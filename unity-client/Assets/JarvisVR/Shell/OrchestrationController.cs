using System.Collections.Generic;
using System.Text;
using UnityEngine;
using TMPro;
using JarvisVR.Net;
using JarvisVR.Protocol;
using JarvisVR.Holograms;

namespace JarvisVR.Shell
{
    /// <summary>
    /// Holographic **Agent Team** view of the live multi-agent orchestration (docs/PROTOCOL.md §9) with
    /// a folded-in **per-agent trace timeline** (§10.1). On <c>orchestration.plan</c> it builds a
    /// spatial org-chart (Jarvis root, specialists below, edges by parent/level); on
    /// <c>orchestration.agent_status</c> each node animates by state; on <c>orchestration.handoff</c> a
    /// sub-agent node + edge are added. Selecting (tap/gaze) a node opens a scrollable **timeline** of
    /// that agent's <c>orchestration.trace_event</c>s (icon per kind, label, skill/tool, duration), and
    /// an Inspect button fetches <c>server.agent_info</c>. Live tracing is gated by
    /// <c>client.trace_subscribe</c> (on while the view is open); past turns load via
    /// <c>client.trace_get</c> → <c>server.trace</c>. Coexists with <see cref="JarvisPresence"/>.
    /// </summary>
    [DisallowMultipleComponent]
    public class OrchestrationController : MonoBehaviour
    {
        public JarvisConnection connection;
        public Transform follow; // head
        [Tooltip("Where the board appears relative to the head (right/up/forward, meters).")]
        public Vector3 headOffset = new Vector3(0.55f, 0.05f, 0.95f);
        public float autoHideDelay = 3.5f;

        public bool IsVisible { get; private set; }

        // ---- testability accessors (read-only views of internal state) ----
        internal int NodeCount => _order.Count;
        internal int EdgeCount => _edges.Count;
        internal bool HasNode(string id) => _nodes.ContainsKey(id);
        internal string NodeState(string id) => _nodes.TryGetValue(id, out var n) ? n.State : null;
        internal int TraceCountFor(string id) => _trace.TryGetValue(id, out var l) ? l.Count : 0;

        // ---- layout constants ----
        private const float RowGap = 0.17f;
        private const float ColGap = 0.24f;
        private const float TopY = 0.1f;
        private const int TraceRows = 9;
        private const int TraceCap = 250;

        // ---- visuals ----
        private GameObject _board;
        private Transform _nodesRoot;
        private Transform _edgesRoot;
        private TextMeshPro _title;
        private TextMeshPro _goalText;

        // timeline
        private GameObject _timeline;
        private TextMeshPro _tlHeader;
        private TextMeshPro _tlHint;
        private GameObject _detailRoot;
        private TextMeshPro _detailText;
        private readonly List<TraceRow> _rows = new List<TraceRow>();

        // ---- state ----
        private readonly Dictionary<string, TeamNode> _nodes = new Dictionary<string, TeamNode>();
        private readonly List<TeamNode> _order = new List<TeamNode>();
        private readonly List<EdgeLine> _edges = new List<EdgeLine>();
        private readonly Dictionary<string, List<AgentTraceEvent>> _trace = new Dictionary<string, List<AgentTraceEvent>>();
        private readonly Dictionary<Transform, string> _cardLookup = new Dictionary<Transform, string>();
        private readonly Dictionary<Transform, string> _tlButtons = new Dictionary<Transform, string>();
        private string _planId;
        private string _selectedAgentId;
        private int _scrollOffset;
        private bool _stickBottom = true;
        private bool _traceSubscribed;
        private float _show;        // 0..1 scale-based fade
        private float _targetShow;
        private float _hideAt;
        private bool _userPinned;
        private bool _layoutDirty;

        private class TeamNode
        {
            public string AgentId, Role, Name, Parent;
            public int Level;
            public bool IsRoot;
            public string State = AgentStates.Queued;
            public string Skill, Label;
            public float Progress, ProgressShown;
            public float Pulse;
            public Vector3 TargetPos;
            public Transform Root;
            public Renderer Card;
            public Material CardMat;
            public Color BaseColor;
            public TextMeshPro NameText, SubText;
            public Transform Spinner;
            public Transform ProgressFill;
        }

        private class EdgeLine { public string From, To; public LineRenderer Line; }
        private class TraceRow { public Transform IconT; public Renderer Icon; public TextMeshPro Text; }

        // ---- lifecycle ----------------------------------------------------------------------

        private void Awake()
        {
            if (connection == null) connection = FindObjectOfType<JarvisConnection>();
            BuildBoard();
            _board.SetActive(false);
        }

        private void OnEnable()
        {
            if (connection == null) return;
            connection.Router.On(MessageTypes.OrchestrationPlan, OnPlan);
            connection.Router.On(MessageTypes.OrchestrationAgentStatus, OnStatus);
            connection.Router.On(MessageTypes.OrchestrationHandoff, OnHandoff);
            connection.Router.On(MessageTypes.OrchestrationTraceEvent, OnTraceEvent);
            connection.Router.On(MessageTypes.ServerTrace, OnServerTrace);
            connection.Router.On(MessageTypes.ServerAgentInfo, OnAgentInfo);
            connection.Router.On(MessageTypes.AgentSpeech, OnSpeech);
        }

        private void OnDisable()
        {
            if (connection == null) return;
            connection.Router.Off(MessageTypes.OrchestrationPlan, OnPlan);
            connection.Router.Off(MessageTypes.OrchestrationAgentStatus, OnStatus);
            connection.Router.Off(MessageTypes.OrchestrationHandoff, OnHandoff);
            connection.Router.Off(MessageTypes.OrchestrationTraceEvent, OnTraceEvent);
            connection.Router.Off(MessageTypes.ServerTrace, OnServerTrace);
            connection.Router.Off(MessageTypes.ServerAgentInfo, OnAgentInfo);
            connection.Router.Off(MessageTypes.AgentSpeech, OnSpeech);
        }

        // ---- message handlers ---------------------------------------------------------------

        private void OnPlan(Envelope env)
        {
            var plan = env.PayloadAs<OrchestrationPlan>();
            if (plan == null) return;

            ClearTeam();
            _planId = plan.PlanId;
            _goalText.text = string.IsNullOrEmpty(plan.Goal) ? "" : $"\u201C{plan.Goal}\u201D";

            if (plan.Agents != null)
                foreach (var a in plan.Agents)
                    EnsureNode(a.AgentId, a.Role, a.Name, a.Parent, a.Level, a.Level == 0 || a.Role == AgentRoles.Orchestrator);

            if (plan.Edges != null && plan.Edges.Count > 0)
                foreach (var e in plan.Edges) EnsureEdge(e.From, e.To);
            else
                foreach (var n in _order) if (!string.IsNullOrEmpty(n.Parent)) EnsureEdge(n.Parent, n.AgentId);

            _layoutDirty = true;
            Show();
            RenderTimeline();
        }

        private void OnStatus(Envelope env)
        {
            var s = env.PayloadAs<AgentStatus>();
            if (s == null || string.IsNullOrEmpty(s.AgentId)) return;

            var node = EnsureNode(s.AgentId, s.Role, null, s.Parent, s.Level, s.Role == AgentRoles.Orchestrator);
            if (!string.IsNullOrEmpty(s.Parent)) EnsureEdge(s.Parent, s.AgentId);

            if (!string.IsNullOrEmpty(s.State)) node.State = s.State;
            node.Skill = s.Skill;
            node.Label = s.Label;
            if (s.Progress.HasValue) node.Progress = Mathf.Clamp01(s.Progress.Value);
            if (node.State == AgentStates.Done) node.Progress = 1f;
            ApplyState(node);

            Show();
            if (AllWorkDone()) ScheduleAutoHide(); else _hideAt = 0f;
        }

        private void OnHandoff(Envelope env)
        {
            var h = env.PayloadAs<AgentHandoff>();
            if (h == null || string.IsNullOrEmpty(h.ToAgent)) return;

            int level = h.Level > 0 ? h.Level : LevelOf(h.FromAgent) + 1;
            var node = EnsureNode(h.ToAgent, h.ToRole, null, h.FromAgent, level, false);
            node.Label = string.IsNullOrEmpty(h.Subtask) ? node.Label : h.Subtask;
            EnsureEdge(h.FromAgent, h.ToAgent);
            ApplyState(node);

            _layoutDirty = true;
            Show();
        }

        private void OnTraceEvent(Envelope env)
        {
            var ev = env.PayloadAs<AgentTraceEvent>();
            if (ev == null || string.IsNullOrEmpty(ev.AgentId)) return;

            if (!_trace.TryGetValue(ev.AgentId, out var list))
            {
                list = new List<AgentTraceEvent>();
                _trace[ev.AgentId] = list;
            }
            list.Add(ev);
            if (list.Count > TraceCap) list.RemoveAt(0);

            // surface activity even if the plan message was missed
            if (!_nodes.ContainsKey(ev.AgentId))
            {
                EnsureNode(ev.AgentId, ev.Role, null, ev.Parent, ev.Level, ev.Role == AgentRoles.Orchestrator);
                if (!string.IsNullOrEmpty(ev.Parent)) EnsureEdge(ev.Parent, ev.AgentId);
                Show();
            }

            if (string.IsNullOrEmpty(_selectedAgentId)) SelectNode(ev.AgentId);
            else if (ev.AgentId == _selectedAgentId) RenderTimeline();
        }

        private void OnServerTrace(Envelope env)
        {
            var t = env.PayloadAs<ServerTrace>();
            if (t == null) return;

            ClearTeam();
            _planId = t.PlanId;
            _goalText.text = string.IsNullOrEmpty(t.Goal) ? "(past turn)" : $"\u201C{t.Goal}\u201D";

            if (t.Agents != null)
                foreach (var a in t.Agents)
                {
                    var node = EnsureNode(a.AgentId, a.Role, null, a.Parent, a.Level, a.Level == 0 || a.Role == AgentRoles.Orchestrator);
                    if (!string.IsNullOrEmpty(a.Parent)) EnsureEdge(a.Parent, a.AgentId);
                    node.State = AgentStates.Done; // a fetched past turn is complete
                    node.Progress = 1f;
                    ApplyState(node);
                }

            if (t.Entries != null)
                foreach (var e in t.Entries)
                {
                    if (string.IsNullOrEmpty(e.AgentId)) continue;
                    if (!_trace.TryGetValue(e.AgentId, out var list)) { list = new List<AgentTraceEvent>(); _trace[e.AgentId] = list; }
                    list.Add(e);
                }

            _layoutDirty = true;
            _userPinned = true; // viewing history — don't auto-hide
            Show();
            SelectNode(FindRootId());
        }

        private void OnAgentInfo(Envelope env)
        {
            var info = env.PayloadAs<ServerAgentInfo>();
            if (info == null) return;
            ShowDetail(BuildDetailText(info));
        }

        private void OnSpeech(Envelope env)
        {
            var sp = env.PayloadAs<AgentSpeech>();
            if (sp != null && sp.Final && _order.Count > 0) ScheduleAutoHide();
        }

        // ---- team model ---------------------------------------------------------------------

        private TeamNode EnsureNode(string id, string role, string name, string parent, int level, bool isRoot)
        {
            if (string.IsNullOrEmpty(id)) return null;
            if (_nodes.TryGetValue(id, out var existing))
            {
                if (!string.IsNullOrEmpty(role)) existing.Role = role;
                if (!string.IsNullOrEmpty(name)) { existing.Name = name; if (existing.NameText) existing.NameText.text = name; }
                if (!string.IsNullOrEmpty(parent)) existing.Parent = parent;
                return existing;
            }

            var node = CreateNode(id, role, name, parent, level, isRoot);
            _nodes[id] = node;
            _order.Add(node);
            _layoutDirty = true;
            return node;
        }

        private TeamNode CreateNode(string id, string role, string name, string parent, int level, bool isRoot)
        {
            var node = new TeamNode
            {
                AgentId = id,
                Role = role,
                Name = !string.IsNullOrEmpty(name) ? name : Prettify(role),
                Parent = parent,
                Level = level,
                IsRoot = isRoot,
            };

            node.Root = new GameObject($"node_{id}").transform;
            node.Root.SetParent(_nodesRoot, false);

            Vector2 size = isRoot ? new Vector2(0.24f, 0.11f) : new Vector2(0.2f, 0.1f);
            node.BaseColor = StateColor(node.State, isRoot);
            var card = MakeCube("card", Vector3.zero, new Vector3(size.x, size.y, 0.012f), node.BaseColor, node.Root, keepCollider: true);
            node.Card = card.GetComponent<Renderer>();
            node.CardMat = node.Card.material;
            _cardLookup[card] = id; // selectable for the trace timeline

            node.NameText = MakeText("name", node.Name, isRoot ? 0.03f : 0.026f, Color.white,
                new Vector3(0f, size.y * 0.5f - 0.024f, -0.013f), new Vector2(size.x * 0.95f, 0.035f), node.Root);
            node.SubText = MakeText("sub", "queued", 0.02f, new Color(0.85f, 0.9f, 1f),
                new Vector3(0f, -0.005f, -0.013f), new Vector2(size.x * 0.95f, 0.045f), node.Root);

            MakeCube("bar_bg", new Vector3(0f, -size.y * 0.5f + 0.014f, -0.013f), new Vector3(size.x * 0.82f, 0.008f, 0.004f), new Color(0.2f, 0.22f, 0.27f), node.Root);
            float barW = size.x * 0.82f;
            node.ProgressFill = MakeCube("bar_fill", new Vector3(-barW * 0.5f, -size.y * 0.5f + 0.014f, -0.015f), new Vector3(0.001f, 0.008f, 0.005f), new Color(0.3f, 0.8f, 1f), node.Root);

            node.Spinner = MakeCube("spinner", new Vector3(size.x * 0.5f - 0.02f, size.y * 0.5f - 0.02f, -0.014f), new Vector3(0.02f, 0.02f, 0.006f), new Color(0.9f, 0.95f, 1f), node.Root);
            node.Spinner.gameObject.SetActive(false);

            ApplyState(node);
            return node;
        }

        private void EnsureEdge(string from, string to)
        {
            if (string.IsNullOrEmpty(from) || string.IsNullOrEmpty(to)) return;
            foreach (var e in _edges) if (e.From == from && e.To == to) return;

            var go = new GameObject($"edge_{from}_{to}");
            go.transform.SetParent(_edgesRoot, false);
            go.transform.localPosition = Vector3.zero;
            go.transform.localRotation = Quaternion.identity;
            var lr = go.AddComponent<LineRenderer>();
            lr.useWorldSpace = false;
            lr.positionCount = 2;
            lr.numCapVertices = 2;
            lr.startWidth = lr.endWidth = 0.006f;
            lr.textureMode = LineTextureMode.Stretch;
            lr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            lr.receiveShadows = false;
            var col = new Color(0.45f, 0.55f, 0.75f, 0.8f);
            lr.material = HoloMaterials.Solid(col);
            lr.startColor = lr.endColor = col;
            _edges.Add(new EdgeLine { From = from, To = to, Line = lr });
        }

        private void ClearTeam()
        {
            foreach (var n in _order) if (n?.Root != null) Destroy(n.Root.gameObject);
            foreach (var e in _edges) if (e?.Line != null) Destroy(e.Line.gameObject);
            _nodes.Clear();
            _order.Clear();
            _edges.Clear();
            _cardLookup.Clear();
            _trace.Clear();
            _selectedAgentId = null;
            _planId = null;
            HideDetail();
            RenderTimeline();
        }

        private int LevelOf(string id) => _nodes.TryGetValue(id, out var n) ? n.Level : 0;

        private string FindRootId()
        {
            foreach (var n in _order) if (n.IsRoot) return n.AgentId;
            return _order.Count > 0 ? _order[0].AgentId : null;
        }

        private bool AllWorkDone()
        {
            bool anyWorker = false, allWorkersDone = true, anyNode = false;
            foreach (var n in _order)
            {
                anyNode = true;
                if (n.IsRoot) continue;
                anyWorker = true;
                if (!AgentStates.IsTerminal(n.State)) allWorkersDone = false;
            }
            if (anyWorker) return allWorkersDone;
            if (!anyNode) return false;
            foreach (var n in _order) if (!AgentStates.IsTerminal(n.State)) return false;
            return true;
        }

        // ---- node visuals + layout ----------------------------------------------------------

        private void ApplyState(TeamNode node)
        {
            node.BaseColor = StateColor(node.State, node.IsRoot);
            node.NameText.text = node.Name;

            string sub = !string.IsNullOrEmpty(node.Label) ? node.Label
                       : !string.IsNullOrEmpty(node.Skill) ? node.Skill
                       : PrettyState(node.State);
            node.SubText.text = sub;

            bool active = IsActiveState(node.State);
            if (node.Spinner != null) node.Spinner.gameObject.SetActive(active);
            if (node.SubText != null)
                node.SubText.color = node.State == AgentStates.Failed ? new Color(1f, 0.7f, 0.7f) : new Color(0.85f, 0.9f, 1f);
        }

        private void Layout()
        {
            var byLevel = new Dictionary<int, List<TeamNode>>();
            foreach (var n in _order)
            {
                if (!byLevel.TryGetValue(n.Level, out var list)) { list = new List<TeamNode>(); byLevel[n.Level] = list; }
                list.Add(n);
            }
            foreach (var kv in byLevel)
            {
                var list = kv.Value;
                int count = list.Count;
                for (int i = 0; i < count; i++)
                {
                    float x = (i - (count - 1) * 0.5f) * ColGap;
                    float y = TopY - kv.Key * RowGap;
                    list[i].TargetPos = new Vector3(x, y, 0f);
                }
            }
            _layoutDirty = false;
        }

        private void Update()
        {
            _show = Mathf.MoveTowards(_show, _targetShow, Time.deltaTime * 4f);
            if (_board.activeSelf)
                _board.transform.localScale = Vector3.one * Mathf.Max(0.0001f, _show);
            if (_targetShow <= 0f && _show <= 0.01f && _board.activeSelf)
                _board.SetActive(false);

            if (!_board.activeSelf) return;

            if (_layoutDirty) Layout();

            float dt = Time.deltaTime;
            foreach (var n in _order)
            {
                if (n.Root == null) continue;
                n.Root.localPosition = Vector3.Lerp(n.Root.localPosition, n.TargetPos, dt * 8f);

                bool active = IsActiveState(n.State);
                n.Pulse += dt * 3f;

                float emis = active ? 0.4f + 0.35f * (Mathf.Sin(n.Pulse) * 0.5f + 0.5f)
                                    : (n.State == AgentStates.Queued ? 0.12f : 0.5f);
                Color c = n.BaseColor;
                HoloMaterials.SetAlbedo(n.CardMat, c);
                if (n.CardMat.HasProperty("_EmissionColor")) n.CardMat.SetColor("_EmissionColor", c * emis);

                if (n.Spinner != null && n.Spinner.gameObject.activeSelf)
                    n.Spinner.Rotate(0f, 0f, -180f * dt, Space.Self);

                if (n.ProgressFill != null)
                {
                    n.ProgressShown = Mathf.Lerp(n.ProgressShown, n.Progress, dt * 6f);
                    float barW = (n.IsRoot ? 0.24f : 0.2f) * 0.82f;
                    float w = Mathf.Clamp01(n.ProgressShown) * barW;
                    var sc = n.ProgressFill.localScale;
                    n.ProgressFill.localScale = new Vector3(Mathf.Max(0.001f, w), sc.y, sc.z);
                    n.ProgressFill.localPosition = new Vector3(-barW * 0.5f + w * 0.5f, n.ProgressFill.localPosition.y, n.ProgressFill.localPosition.z);
                    bool showFill = (active || n.State == AgentStates.Done) && n.Progress > 0.001f;
                    if (n.ProgressFill.gameObject.activeSelf != showFill) n.ProgressFill.gameObject.SetActive(showFill);
                }
            }

            UpdateEdges();

#if ENABLE_LEGACY_INPUT_MANAGER
            HandleInput();
#endif

            if (_hideAt > 0f && Time.time >= _hideAt) { _hideAt = 0f; Hide(); }
        }

        private void UpdateEdges()
        {
            for (int i = _edges.Count - 1; i >= 0; i--)
            {
                var e = _edges[i];
                if (e.Line == null) continue;
                if (!_nodes.TryGetValue(e.From, out var from) || !_nodes.TryGetValue(e.To, out var to)) { e.Line.enabled = false; continue; }
                e.Line.enabled = true;
                e.Line.SetPosition(0, from.Root.localPosition + new Vector3(0, 0, 0.004f));
                e.Line.SetPosition(1, to.Root.localPosition + new Vector3(0, 0, 0.004f));
            }
        }

        // ---- trace timeline -----------------------------------------------------------------

        /// <summary>Select an agent node to show its trace timeline (tap / gaze / Meta poke).</summary>
        public void SelectNode(string agentId)
        {
            _selectedAgentId = agentId;
            _stickBottom = true;
            HideDetail();
            RenderTimeline();
        }

        /// <summary>Handle a timeline button by element id (mouse tester / Meta poke / gaze).</summary>
        public void PressTimeline(string element)
        {
            switch (element)
            {
                case "tl_up": _stickBottom = false; _scrollOffset = Mathf.Max(0, _scrollOffset - 1); RenderTimeline(); break;
                case "tl_down": _scrollOffset += 1; RenderTimeline(); break;
                case "tl_close": _selectedAgentId = null; HideDetail(); RenderTimeline(); break;
                case "tl_last": connection?.Send(MessageTypes.ClientTraceGet, new TraceGet()); break;
                case "tl_inspect":
                    if (_detailRoot != null && _detailRoot.activeSelf) { HideDetail(); }
                    else if (!string.IsNullOrEmpty(_selectedAgentId))
                    {
                        connection?.Send(MessageTypes.ClientAgentInspect, new AgentInspect { AgentId = _selectedAgentId });
                        ShowDetail("Loading\u2026");
                    }
                    break;
            }
        }

        private void RenderTimeline()
        {
            if (_tlHeader == null) return;

            // node-name highlight for the selected agent
            foreach (var n in _order)
                if (n.NameText != null) n.NameText.color = (n.AgentId == _selectedAgentId) ? new Color(1f, 0.85f, 0.35f) : Color.white;

            if (string.IsNullOrEmpty(_selectedAgentId))
            {
                _tlHeader.text = "Trace";
                if (_tlHint != null) _tlHint.gameObject.SetActive(true);
                foreach (var r in _rows) SetRow(r, false, default, null);
                return;
            }

            if (_tlHint != null) _tlHint.gameObject.SetActive(false);
            string name = _nodes.TryGetValue(_selectedAgentId, out var node) ? node.Name : _selectedAgentId;
            _tlHeader.text = $"Trace \u00B7 {name}";

            List<AgentTraceEvent> entries = _trace.TryGetValue(_selectedAgentId, out var list) ? list : null;
            int count = entries?.Count ?? 0;
            int maxOffset = Mathf.Max(0, count - TraceRows);
            if (_stickBottom) _scrollOffset = maxOffset;
            _scrollOffset = Mathf.Clamp(_scrollOffset, 0, maxOffset);
            if (_scrollOffset >= maxOffset) _stickBottom = true;

            for (int i = 0; i < _rows.Count; i++)
            {
                int idx = _scrollOffset + i;
                if (entries != null && idx < count) SetRow(_rows[i], true, KindColor(entries[idx].Kind), FormatEntry(entries[idx]), IsError(entries[idx].Kind));
                else SetRow(_rows[i], false, default, null);
            }
        }

        private void SetRow(TraceRow row, bool active, Color iconColor, string text, bool error = false)
        {
            if (row == null) return;
            if (row.IconT != null && row.IconT.gameObject.activeSelf != active) row.IconT.gameObject.SetActive(active);
            if (row.Text != null)
            {
                row.Text.gameObject.SetActive(active);
                if (active) { row.Text.text = text; row.Text.color = error ? new Color(1f, 0.6f, 0.55f) : new Color(0.9f, 0.93f, 1f); }
            }
            if (active && row.Icon != null) HoloMaterials.SetAlbedo(row.Icon.material, iconColor);
        }

        private static string FormatEntry(AgentTraceEvent e)
        {
            string main = string.IsNullOrEmpty(e.Label) ? KindCode(e.Kind) : e.Label;
            string tt = !string.IsNullOrEmpty(e.Tool) ? e.Tool : e.Skill;
            string suffix = !string.IsNullOrEmpty(tt) ? $"  \u00B7{tt}" : "";
            string dur = (e.DurationMs.HasValue && e.DurationMs.Value > 0) ? $"  {e.DurationMs.Value}ms" : "";
            return $"[{KindCode(e.Kind)}] {main}{suffix}{dur}";
        }

        private void ShowDetail(string text)
        {
            if (_detailRoot == null) return;
            _detailRoot.SetActive(true);
            if (_detailText != null) _detailText.text = text;
        }

        private void HideDetail()
        {
            if (_detailRoot != null) _detailRoot.SetActive(false);
        }

        private static string BuildDetailText(ServerAgentInfo info)
        {
            var sb = new StringBuilder();
            sb.Append($"<b>{info.Name ?? info.Role}</b>");
            if (!string.IsNullOrEmpty(info.Role)) sb.Append($"  <size=70%>({info.Role})</size>");
            if (!string.IsNullOrEmpty(info.Source)) sb.Append($"  <size=70%>[{info.Source}]</size>");
            sb.Append('\n');
            if (!string.IsNullOrEmpty(info.Persona)) sb.Append(info.Persona).Append('\n');
            if (info.Tools != null && info.Tools.Count > 0) sb.Append($"<b>Tools:</b> {string.Join(", ", info.Tools)}\n");
            if (info.Skills != null && info.Skills.Count > 0)
            {
                var names = new List<string>();
                foreach (var s in info.Skills) names.Add(s.Name);
                sb.Append($"<b>Skills:</b> {string.Join(", ", names)}\n");
            }
            if (info.Memory != null)
                sb.Append($"<b>Memory:</b> {info.Memory.Summary} ({info.Memory.Items} items)");
            return sb.ToString();
        }

        // ---- show / hide / toggle -----------------------------------------------------------

        public void Show()
        {
            bool wasHidden = !_board.activeSelf;
            _board.SetActive(true);
            _targetShow = 1f;
            _hideAt = 0f;
            if (wasHidden)
            {
                _show = 0.0001f;
                PlaceInFront();
                SetTraceSubscribed(true); // live trace only while the view is open (§10.1)
            }
            IsVisible = true;
        }

        public void Hide()
        {
            _targetShow = 0f;
            IsVisible = false;
            SetTraceSubscribed(false);
        }

        public void Toggle()
        {
            if (IsVisible) { _userPinned = false; Hide(); return; }
            _userPinned = true;
            if (_order.Count == 0) _goalText.text = "Waiting for a task\u2026";
            Show();
        }

        private void SetTraceSubscribed(bool enabled)
        {
            if (enabled == _traceSubscribed) return;
            _traceSubscribed = enabled;
            connection?.Send(MessageTypes.ClientTraceSubscribe, new TraceSubscribe(enabled));
        }

        private void ScheduleAutoHide()
        {
            if (_userPinned) return;
            if (_hideAt <= 0f) _hideAt = Time.time + autoHideDelay;
        }

        private void PlaceInFront()
        {
            var head = follow != null ? follow : (Camera.main != null ? Camera.main.transform : null);
            if (head == null) return;
            transform.position = head.position + head.forward * headOffset.z + head.right * headOffset.x + head.up * headOffset.y;
            transform.rotation = Quaternion.LookRotation(transform.position - head.position);
        }

#if ENABLE_LEGACY_INPUT_MANAGER
        private void HandleInput()
        {
            if (!Input.GetMouseButtonDown(0)) return;
            var cam = Camera.main;
            if (cam == null) return;
            if (!Physics.Raycast(cam.ScreenPointToRay(Input.mousePosition), out var hit, 20f)) return;
            if (_cardLookup.TryGetValue(hit.collider.transform, out var aid)) { SelectNode(aid); return; }
            if (_tlButtons.TryGetValue(hit.collider.transform, out var el)) PressTimeline(el);
        }
#endif

        // ---- construction helpers -----------------------------------------------------------

        private void BuildBoard()
        {
            _board = new GameObject("TeamBoard");
            _board.transform.SetParent(transform, false);

            MakeCube("bg", new Vector3(0f, -0.04f, 0.01f), new Vector3(0.78f, 0.5f, 0.008f), new Color(0.05f, 0.06f, 0.09f, 0.9f), _board.transform);
            _title = MakeText("title", "Agent Team", 0.034f, new Color(0.7f, 0.85f, 1f), new Vector3(0f, 0.2f, -0.006f), new Vector2(0.7f, 0.05f), _board.transform);
            _goalText = MakeText("goal", "", 0.022f, new Color(0.7f, 0.75f, 0.85f), new Vector3(0f, 0.16f, -0.006f), new Vector2(0.74f, 0.04f), _board.transform);

            _edgesRoot = new GameObject("edges").transform;
            _edgesRoot.SetParent(_board.transform, false);
            _nodesRoot = new GameObject("nodes").transform;
            _nodesRoot.SetParent(_board.transform, false);

            BuildTimeline();

            var bb = gameObject.AddComponent<Billboard>();
            bb.yawOnly = false;
        }

        private void BuildTimeline()
        {
            _timeline = new GameObject("Timeline");
            _timeline.transform.SetParent(_board.transform, false);
            _timeline.transform.localPosition = new Vector3(0.66f, -0.02f, 0f);

            MakeCube("tl_bg", new Vector3(0f, 0f, 0.01f), new Vector3(0.46f, 0.54f, 0.008f), new Color(0.04f, 0.05f, 0.08f, 0.92f), _timeline.transform);
            _tlHeader = MakeText("tl_header", "Trace", 0.026f, new Color(0.7f, 0.85f, 1f), new Vector3(0f, 0.23f, -0.006f), new Vector2(0.44f, 0.04f), _timeline.transform);
            _tlHint = MakeText("tl_hint", "Tap an agent node to see its trace", 0.02f, new Color(0.6f, 0.65f, 0.75f), new Vector3(0f, 0.0f, -0.006f), new Vector2(0.42f, 0.06f), _timeline.transform);

            TimelineButton("tl_inspect", "Inspect", new Vector3(-0.15f, 0.185f, -0.006f), new Vector3(0.11f, 0.038f, 0.012f), new Color(0.25f, 0.3f, 0.45f));
            TimelineButton("tl_last", "Last", new Vector3(-0.035f, 0.185f, -0.006f), new Vector3(0.09f, 0.038f, 0.012f), new Color(0.25f, 0.35f, 0.4f));
            TimelineButton("tl_up", "\u2191", new Vector3(0.06f, 0.185f, -0.006f), new Vector3(0.045f, 0.038f, 0.012f), new Color(0.22f, 0.26f, 0.36f));
            TimelineButton("tl_down", "\u2193", new Vector3(0.115f, 0.185f, -0.006f), new Vector3(0.045f, 0.038f, 0.012f), new Color(0.22f, 0.26f, 0.36f));
            TimelineButton("tl_close", "\u2715", new Vector3(0.185f, 0.185f, -0.006f), new Vector3(0.05f, 0.038f, 0.012f), new Color(0.4f, 0.28f, 0.32f));

            float top = 0.13f, rowH = 0.032f;
            for (int i = 0; i < TraceRows; i++)
            {
                float y = top - i * rowH;
                var icon = MakeCube($"tl_icon_{i}", new Vector3(-0.205f, y, -0.006f), new Vector3(0.016f, 0.016f, 0.006f), new Color(0.4f, 0.5f, 0.7f), _timeline.transform);
                var text = MakeText($"tl_row_{i}", "", 0.0165f, new Color(0.9f, 0.93f, 1f), new Vector3(0.01f, y, -0.006f), new Vector2(0.4f, rowH), _timeline.transform, TextAlignmentOptions.Left);
                _rows.Add(new TraceRow { IconT = icon, Icon = icon.GetComponent<Renderer>(), Text = text });
                icon.gameObject.SetActive(false);
                text.gameObject.SetActive(false);
            }

            // agent_info detail overlay (hidden until Inspect)
            _detailRoot = new GameObject("tl_detail");
            _detailRoot.transform.SetParent(_timeline.transform, false);
            MakeCube("detail_bg", new Vector3(0f, -0.02f, -0.005f), new Vector3(0.44f, 0.4f, 0.006f), new Color(0.07f, 0.08f, 0.12f, 0.98f), _detailRoot.transform);
            _detailText = MakeText("detail_text", "", 0.018f, new Color(0.9f, 0.93f, 1f), new Vector3(0f, -0.02f, -0.012f), new Vector2(0.42f, 0.38f), _detailRoot.transform, TextAlignmentOptions.TopLeft);
            _detailText.enableWordWrapping = true;
            _detailRoot.SetActive(false);
        }

        private void TimelineButton(string element, string label, Vector3 pos, Vector3 scale, Color color)
        {
            var btn = MakeCube($"btn_{element}", pos, scale, color, _timeline.transform, keepCollider: true);
            _tlButtons[btn] = element;
            MakeText($"lbl_{element}", label, Mathf.Min(0.02f, scale.y * 0.55f), Color.white, pos + new Vector3(0, 0, -scale.z), new Vector2(scale.x, scale.y), _timeline.transform);
        }

        private Transform MakeCube(string name, Vector3 pos, Vector3 scale, Color color, Transform parent, bool keepCollider = false)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = name;
            if (!keepCollider) { var col = go.GetComponent<Collider>(); if (col != null) Destroy(col); }
            go.transform.SetParent(parent, false);
            go.transform.localPosition = pos;
            go.transform.localScale = scale;
            var r = go.GetComponent<Renderer>();
            if (r != null) r.material = HoloMaterials.Solid(color);
            return go.transform;
        }

        private TextMeshPro MakeText(string name, string text, float size, Color color, Vector3 pos, Vector2 rect, Transform parent,
            TextAlignmentOptions align = TextAlignmentOptions.Center)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.transform.localPosition = pos;
            var tmp = go.AddComponent<TextMeshPro>();
            tmp.text = text;
            tmp.fontSize = size;
            tmp.color = color;
            tmp.alignment = align;
            tmp.enableWordWrapping = false;
            tmp.overflowMode = TextOverflowModes.Ellipsis;
            tmp.rectTransform.sizeDelta = rect;
            return tmp;
        }

        // ---- helpers ------------------------------------------------------------------------

        internal static bool IsActiveState(string state)
            => state == AgentStates.Working || state == AgentStates.Planning || state == AgentStates.Delegating;

        private static string PrettyState(string state) => string.IsNullOrEmpty(state) ? "queued" : state;

        private static bool IsError(string kind) => kind == TraceKinds.Error;

        internal static string KindCode(string kind)
        {
            switch (kind)
            {
                case TraceKinds.MemoryRead: return "mem";
                case TraceKinds.MemoryWrite: return "mem+";
                case TraceKinds.SkillActivated: return "skill";
                case TraceKinds.ToolCall: return "tool";
                case TraceKinds.ToolResult: return "\u2713";
                case TraceKinds.Observation: return "obs";
                case TraceKinds.Delegated: return "deleg";
                case TraceKinds.Speech: return "say";
                case TraceKinds.Error: return "err";
                default: return kind ?? "?";
            }
        }

        internal static Color KindColor(string kind)
        {
            switch (kind)
            {
                case TraceKinds.MemoryRead:
                case TraceKinds.MemoryWrite: return new Color(0.3f, 0.8f, 0.9f);
                case TraceKinds.SkillActivated: return new Color(1f, 0.8f, 0.3f);
                case TraceKinds.ToolCall: return new Color(0.3f, 0.6f, 1f);
                case TraceKinds.ToolResult: return new Color(0.3f, 0.85f, 0.45f);
                case TraceKinds.Observation: return new Color(0.7f, 0.5f, 1f);
                case TraceKinds.Delegated: return new Color(0.6f, 0.4f, 0.95f);
                case TraceKinds.Speech: return new Color(0.3f, 0.9f, 0.7f);
                case TraceKinds.Error: return new Color(0.95f, 0.35f, 0.3f);
                default: return new Color(0.5f, 0.55f, 0.65f);
            }
        }

        internal static Color StateColor(string state, bool isRoot)
        {
            switch (state)
            {
                case AgentStates.Queued: return new Color(0.35f, 0.37f, 0.43f);
                case AgentStates.Planning: return new Color(0.3f, 0.55f, 0.95f);
                case AgentStates.Working: return new Color(0.2f, 0.65f, 1f);
                case AgentStates.Delegating: return new Color(0.7f, 0.45f, 1f);
                case AgentStates.Waiting: return new Color(0.85f, 0.7f, 0.3f);
                case AgentStates.Done: return new Color(0.3f, 0.85f, 0.45f);
                case AgentStates.Failed: return new Color(0.9f, 0.32f, 0.3f);
                default: return isRoot ? new Color(1f, 0.78f, 0.3f) : new Color(0.4f, 0.45f, 0.55f);
            }
        }

        internal static string Prettify(string role)
        {
            if (string.IsNullOrEmpty(role)) return "Agent";
            if (role == AgentRoles.Orchestrator || role == "jarvis") return "Jarvis";
            var sb = new StringBuilder();
            foreach (var part in role.Split('-'))
            {
                if (part.Length == 0 || part == "agent") continue;
                sb.Append(char.ToUpperInvariant(part[0]));
                if (part.Length > 1) sb.Append(part.Substring(1));
                sb.Append(' ');
            }
            var s = sb.ToString().Trim();
            return s.Length == 0 ? role : s;
        }
    }
}
