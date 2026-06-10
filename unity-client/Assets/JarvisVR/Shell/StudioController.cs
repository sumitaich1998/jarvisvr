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
    /// In-headset **Studio** to compose your own agents & Agent Skills (docs/PROTOCOL.md §10.2).
    /// On open it sends <c>client.author_list</c> and renders the catalog (agents + skills, badged
    /// builtin/user). New/Edit forms author via <c>client.author_skill</c> / <c>client.author_agent</c>
    /// (op create|update|delete); the server validates + hot-reloads and replies with
    /// <c>server.authoring</c> (refresh) or <c>server.error</c> (shown inline). Text is entered via the
    /// shared <see cref="VrKeyboard"/> (multiline for skill bodies / personas). Procedural panels,
    /// consistent with Settings/Team.
    /// </summary>
    [DisallowMultipleComponent]
    public class StudioController : MonoBehaviour
    {
        public JarvisConnection connection;
        public VrKeyboard keyboard;
        public Transform follow; // head

        public bool IsVisible { get; private set; }

        private const int ListRows = 6;
        private const int ChipRows = 5;

        private enum Mode { Main, Skill, Agent }
        private Mode _mode = Mode.Main;

        // ---- catalog ----
        private readonly List<AuthoringAgent> _agents = new List<AuthoringAgent>();
        private readonly List<AuthoringSkill> _skills = new List<AuthoringSkill>();
        private readonly List<string> _categories = new List<string>();
        private readonly List<string> _tools = new List<string>();
        private string _pendingOp; // "skill" | "agent" | null

        // ---- skill working state ----
        private string _skOp, _skName = "", _skCategory = "", _skAgent = "", _skDesc = "", _skBody = "", _skLicense = "";
        private readonly HashSet<string> _skTools = new HashSet<string>();
        private bool _skIsUser;
        private int _skToolsOff;

        // ---- agent working state ----
        private string _agOp, _agRole = "", _agName = "", _agPersona = "";
        private readonly HashSet<string> _agTools = new HashSet<string>();
        private readonly HashSet<string> _agSkills = new HashSet<string>();
        private bool _agIsUser;
        private int _agToolsOff, _agSkillsOff;

        // ---- scroll ----
        private int _agentsOff, _skillsOff;

        // ---- visuals ----
        private GameObject _root, _mainPanel, _skillPanel, _agentPanel;
        private readonly Dictionary<Transform, string> _buttons = new Dictionary<Transform, string>();
        private TextMeshPro _mainStatus, _skStatus, _agStatus;
        private readonly List<RowRef> _agentRows = new List<RowRef>();
        private readonly List<RowRef> _skillRows = new List<RowRef>();
        private readonly List<ChipRef> _skToolRows = new List<ChipRef>();
        private readonly List<ChipRef> _agToolRows = new List<ChipRef>();
        private readonly List<ChipRef> _agSkillRows = new List<ChipRef>();
        private TextMeshPro _skNameV, _skCatV, _skAgentV, _skDescV, _skBodyV, _skHeader;
        private TextMeshPro _agRoleV, _agNameV, _agPersonaV, _agHeader;
        private Transform _skDeleteBtn, _agDeleteBtn;

        private class RowRef { public Transform Btn; public TextMeshPro Text; }
        private class ChipRef { public Transform Btn; public Renderer Mat; public TextMeshPro Text; }

        // ---- lifecycle ----------------------------------------------------------------------

        private void Awake()
        {
            if (connection == null) connection = FindObjectOfType<JarvisConnection>();
            if (keyboard == null) keyboard = FindObjectOfType<VrKeyboard>();
            BuildUI();
            _root.SetActive(false);
        }

        private void OnEnable()
        {
            if (connection == null) return;
            connection.Router.On(MessageTypes.ServerAuthoring, OnAuthoring);
            connection.Router.On(MessageTypes.ServerError, OnServerError);
        }

        private void OnDisable()
        {
            if (connection == null) return;
            connection.Router.Off(MessageTypes.ServerAuthoring, OnAuthoring);
            connection.Router.Off(MessageTypes.ServerError, OnServerError);
        }

        public void Toggle() { if (IsVisible) Hide(); else Open(); }

        public void Open()
        {
            IsVisible = true;
            _pendingOp = null;
            _root.SetActive(true);
            PlaceInFront();
            SetMode(Mode.Main);
            SetStatus(_mainStatus, "Loading\u2026", false);
            connection?.Send(MessageTypes.ClientAuthorList, new AuthorList());
            RenderMain();
        }

        public void Hide()
        {
            IsVisible = false;
            keyboard?.Close();
            if (_root != null) _root.SetActive(false);
        }

        private void PlaceInFront()
        {
            var head = follow != null ? follow : (Camera.main != null ? Camera.main.transform : null);
            if (head == null) return;
            transform.position = head.position + head.forward * 0.8f;
            transform.rotation = Quaternion.LookRotation(transform.position - head.position);
        }

        // ---- protocol handlers --------------------------------------------------------------

        private void OnAuthoring(Envelope env)
        {
            var a = env.PayloadAs<ServerAuthoring>();
            if (a == null) return;

            _agents.Clear(); if (a.Agents != null) _agents.AddRange(a.Agents);
            _skills.Clear(); if (a.Skills != null) _skills.AddRange(a.Skills);
            _categories.Clear(); if (a.Categories != null) _categories.AddRange(a.Categories);
            _tools.Clear(); if (a.Tools != null) _tools.AddRange(a.Tools);

            if (_pendingOp != null)
            {
                var st = _pendingOp == "skill" ? _skStatus : _agStatus;
                SetStatus(st, "Saved \u2713", false);
                _pendingOp = null;
                SetMode(Mode.Main);
            }
            SetStatus(_mainStatus, $"{_agents.Count} agents \u00B7 {_skills.Count} skills", false);
            RenderActive();
        }

        private void OnServerError(Envelope env)
        {
            if (!IsVisible) return;
            var e = env.PayloadAs<ErrorPayload>();
            bool authoringError = e != null && (e.Code == ErrorCodes.InvalidSkill || e.Code == ErrorCodes.InvalidAgent
                || e.Code == ErrorCodes.NameConflict || e.Code == ErrorCodes.Forbidden);
            if (_pendingOp == null && !authoringError) return;
            var st = _mode == Mode.Skill ? _skStatus : _mode == Mode.Agent ? _agStatus : _mainStatus;
            SetStatus(st, "\u26A0 " + (e?.Message ?? e?.Code ?? "error"), true);
            _pendingOp = null;
        }

        // ---- actions ------------------------------------------------------------------------

        /// <summary>Handle a Studio button by element id (mouse tester / Meta poke / gaze).</summary>
        public void Press(string element)
        {
            if (string.IsNullOrEmpty(element)) return;

            if (element.StartsWith("agentsel:")) { OpenAgentEditor(element.Substring(9)); return; }
            if (element.StartsWith("skillsel:")) { OpenSkillEditor(element.Substring(9)); return; }
            if (element.StartsWith("sktool:")) { ToggleSet(_skTools, element.Substring(7)); RenderSkillEditor(); return; }
            if (element.StartsWith("agtool:")) { ToggleSet(_agTools, element.Substring(7)); RenderAgentEditor(); return; }
            if (element.StartsWith("agskill:")) { ToggleSet(_agSkills, element.Substring(8)); RenderAgentEditor(); return; }

            switch (element)
            {
                case "close": Hide(); break;
                case "new_skill": OpenSkillEditor(null); break;
                case "new_agent": OpenAgentEditor(null); break;
                case "agents_up": _agentsOff = Mathf.Max(0, _agentsOff - 1); RenderMain(); break;
                case "agents_down": _agentsOff++; RenderMain(); break;
                case "skills_up": _skillsOff = Mathf.Max(0, _skillsOff - 1); RenderMain(); break;
                case "skills_down": _skillsOff++; RenderMain(); break;

                // skill editor
                case "sk_name": Edit("Skill name (a-z0-9-)", _skName, v => { _skName = Sanitize(v); RenderSkillEditor(); }); break;
                case "sk_cat_prev": _skCategory = Cycle(_categories, _skCategory, -1); RenderSkillEditor(); break;
                case "sk_cat_next": _skCategory = Cycle(_categories, _skCategory, 1); RenderSkillEditor(); break;
                case "sk_agent_prev": _skAgent = Cycle(AgentRoleList(), _skAgent, -1); RenderSkillEditor(); break;
                case "sk_agent_next": _skAgent = Cycle(AgentRoleList(), _skAgent, 1); RenderSkillEditor(); break;
                case "sk_desc": Edit("Description (what + when to use)", _skDesc, v => { _skDesc = v; RenderSkillEditor(); }); break;
                case "sk_body": Edit("Instructions (SKILL.md body)", _skBody, v => { _skBody = v; RenderSkillEditor(); }, multiline: true); break;
                case "sk_tools_up": _skToolsOff = Mathf.Max(0, _skToolsOff - 1); RenderSkillEditor(); break;
                case "sk_tools_down": _skToolsOff++; RenderSkillEditor(); break;
                case "sk_save": SaveSkill(); break;
                case "sk_delete": DeleteSkill(); break;
                case "sk_cancel": SetMode(Mode.Main); RenderMain(); break;

                // agent editor
                case "ag_role": Edit("Agent role id (a-z0-9-)", _agRole, v => { _agRole = Sanitize(v); RenderAgentEditor(); }); break;
                case "ag_name": Edit("Agent name", _agName, v => { _agName = v; RenderAgentEditor(); }); break;
                case "ag_persona": Edit("Persona / system prompt", _agPersona, v => { _agPersona = v; RenderAgentEditor(); }, multiline: true); break;
                case "ag_tools_up": _agToolsOff = Mathf.Max(0, _agToolsOff - 1); RenderAgentEditor(); break;
                case "ag_tools_down": _agToolsOff++; RenderAgentEditor(); break;
                case "ag_skills_up": _agSkillsOff = Mathf.Max(0, _agSkillsOff - 1); RenderAgentEditor(); break;
                case "ag_skills_down": _agSkillsOff++; RenderAgentEditor(); break;
                case "ag_save": SaveAgent(); break;
                case "ag_delete": DeleteAgent(); break;
                case "ag_cancel": SetMode(Mode.Main); RenderMain(); break;
            }
        }

        private void Edit(string label, string initial, System.Action<string> onSubmit, bool multiline = false)
        {
            if (keyboard == null) return;
            keyboard.Open(initial ?? "", false, label, onSubmit, null, multiline);
        }

        private static void ToggleSet(HashSet<string> set, string id)
        {
            if (set.Contains(id)) set.Remove(id); else set.Add(id);
        }

        // ---- skill editor -------------------------------------------------------------------

        private void OpenSkillEditor(string name)
        {
            AuthoringSkill src = null;
            if (!string.IsNullOrEmpty(name))
                foreach (var s in _skills) if (s.Name == name) { src = s; break; }

            _skTools.Clear();
            if (src != null)
            {
                _skIsUser = src.IsUser;
                _skOp = _skIsUser ? AuthorOps.Update : AuthorOps.Create; // fork built-ins into your own
                _skName = src.IsUser ? src.Name : src.Name + "-copy";
                _skCategory = src.Category ?? FirstOr(_categories, "general");
                _skAgent = src.Agent ?? FirstOr(AgentRoleList(), "");
                _skDesc = src.Description ?? "";
                _skBody = src.Body ?? "";
                _skLicense = "MIT";
                if (src.AllowedTools != null) foreach (var t in src.AllowedTools) _skTools.Add(t);
            }
            else
            {
                _skIsUser = false;
                _skOp = AuthorOps.Create;
                _skName = "";
                _skCategory = FirstOr(_categories, "general");
                _skAgent = FirstOr(AgentRoleList(), "");
                _skDesc = "";
                _skBody = "# Skill\n## Steps\n1. ";
                _skLicense = "MIT";
            }
            _skToolsOff = 0;
            SetStatus(_skStatus, src != null && !_skIsUser ? "Forking a built-in skill (saves as new)" : "", false);
            SetMode(Mode.Skill);
            RenderSkillEditor();
        }

        private void SaveSkill()
        {
            if (string.IsNullOrEmpty(_skName)) { SetStatus(_skStatus, "Name required", true); return; }
            var payload = new AuthorSkill
            {
                Op = _skOp,
                Name = _skName,
                Category = _skCategory,
                Agent = _skAgent,
                Description = _skDesc,
                Body = _skBody,
                AllowedTools = new List<string>(_skTools),
                License = _skLicense,
            };
            _pendingOp = "skill";
            SetStatus(_skStatus, "Saving\u2026", false);
            connection?.Send(MessageTypes.ClientAuthorSkill, payload);
        }

        private void DeleteSkill()
        {
            if (!_skIsUser || string.IsNullOrEmpty(_skName)) { SetStatus(_skStatus, "Only user skills can be deleted", true); return; }
            _pendingOp = "skill";
            SetStatus(_skStatus, "Deleting\u2026", false);
            connection?.Send(MessageTypes.ClientAuthorSkill, new AuthorSkill { Op = AuthorOps.Delete, Name = _skName });
        }

        // ---- agent editor -------------------------------------------------------------------

        private void OpenAgentEditor(string role)
        {
            AuthoringAgent src = null;
            if (!string.IsNullOrEmpty(role))
                foreach (var a in _agents) if (a.Role == role) { src = a; break; }

            _agTools.Clear(); _agSkills.Clear();
            if (src != null)
            {
                _agIsUser = src.IsUser;
                _agOp = _agIsUser ? AuthorOps.Update : AuthorOps.Create;
                _agRole = src.IsUser ? src.Role : src.Role + "-copy";
                _agName = src.Name ?? Prettify(src.Role);
                _agPersona = src.Persona ?? "";
                if (src.Tools != null) foreach (var t in src.Tools) _agTools.Add(t);
                if (src.Skills != null) foreach (var s in src.Skills) _agSkills.Add(s);
            }
            else
            {
                _agIsUser = false;
                _agOp = AuthorOps.Create;
                _agRole = "";
                _agName = "";
                _agPersona = "You are a helpful specialist that\u2026";
            }
            _agToolsOff = 0; _agSkillsOff = 0;
            SetStatus(_agStatus, src != null && !_agIsUser ? "Forking a built-in agent (saves as new)" : "", false);
            SetMode(Mode.Agent);
            RenderAgentEditor();
        }

        private void SaveAgent()
        {
            if (string.IsNullOrEmpty(_agRole)) { SetStatus(_agStatus, "Role id required", true); return; }
            var payload = new AuthorAgent
            {
                Op = _agOp,
                Role = _agRole,
                Name = string.IsNullOrEmpty(_agName) ? Prettify(_agRole) : _agName,
                Persona = _agPersona,
                Tools = new List<string>(_agTools),
                Skills = new List<string>(_agSkills),
            };
            _pendingOp = "agent";
            SetStatus(_agStatus, "Saving\u2026", false);
            connection?.Send(MessageTypes.ClientAuthorAgent, payload);
        }

        private void DeleteAgent()
        {
            if (!_agIsUser || string.IsNullOrEmpty(_agRole)) { SetStatus(_agStatus, "Only user agents can be deleted", true); return; }
            _pendingOp = "agent";
            SetStatus(_agStatus, "Deleting\u2026", false);
            connection?.Send(MessageTypes.ClientAuthorAgent, new AuthorAgent { Op = AuthorOps.Delete, Role = _agRole });
        }

        // ---- rendering ----------------------------------------------------------------------

        private void SetMode(Mode m)
        {
            _mode = m;
            _mainPanel.SetActive(m == Mode.Main);
            _skillPanel.SetActive(m == Mode.Skill);
            _agentPanel.SetActive(m == Mode.Agent);
        }

        private void RenderActive()
        {
            if (_mode == Mode.Main) RenderMain();
            else if (_mode == Mode.Skill) RenderSkillEditor();
            else RenderAgentEditor();
        }

        private void RenderMain()
        {
            // agents column
            int aMax = Mathf.Max(0, _agents.Count - ListRows);
            _agentsOff = Mathf.Clamp(_agentsOff, 0, aMax);
            for (int i = 0; i < _agentRows.Count; i++)
            {
                int idx = _agentsOff + i;
                var row = _agentRows[i];
                if (idx < _agents.Count)
                {
                    var a = _agents[idx];
                    row.Btn.gameObject.SetActive(true);
                    row.Text.text = $"{(a.Name ?? Prettify(a.Role))} {Badge(a.Source)}";
                    _buttons[row.Btn] = "agentsel:" + a.Role;
                }
                else { row.Btn.gameObject.SetActive(false); _buttons[row.Btn] = ""; }
            }

            // skills column
            int sMax = Mathf.Max(0, _skills.Count - ListRows);
            _skillsOff = Mathf.Clamp(_skillsOff, 0, sMax);
            for (int i = 0; i < _skillRows.Count; i++)
            {
                int idx = _skillsOff + i;
                var row = _skillRows[i];
                if (idx < _skills.Count)
                {
                    var s = _skills[idx];
                    row.Btn.gameObject.SetActive(true);
                    row.Text.text = $"{s.Name} {Badge(s.Source)}";
                    _buttons[row.Btn] = "skillsel:" + s.Name;
                }
                else { row.Btn.gameObject.SetActive(false); _buttons[row.Btn] = ""; }
            }
        }

        private void RenderSkillEditor()
        {
            _skHeader.text = _skOp == AuthorOps.Update ? $"Edit Skill \u00B7 {_skName}" : "New Skill";
            _skNameV.text = string.IsNullOrEmpty(_skName) ? "(tap to set)" : _skName;
            _skCatV.text = string.IsNullOrEmpty(_skCategory) ? "(none)" : _skCategory;
            _skAgentV.text = string.IsNullOrEmpty(_skAgent) ? "(none)" : _skAgent;
            _skDescV.text = string.IsNullOrEmpty(_skDesc) ? "(tap to set)" : Truncate(_skDesc, 60);
            _skBodyV.text = $"Body: {_skBody.Length} chars";
            if (_skDeleteBtn != null) _skDeleteBtn.gameObject.SetActive(_skIsUser && _skOp == AuthorOps.Update);
            RenderChips(_skToolRows, _tools, _skToolsOff, _skTools, "sktool:");
        }

        private void RenderAgentEditor()
        {
            _agHeader.text = _agOp == AuthorOps.Update ? $"Edit Agent \u00B7 {_agRole}" : "New Agent";
            _agRoleV.text = string.IsNullOrEmpty(_agRole) ? "(tap to set)" : _agRole;
            _agNameV.text = string.IsNullOrEmpty(_agName) ? "(tap to set)" : _agName;
            _agPersonaV.text = $"Persona: {_agPersona.Length} chars";
            if (_agDeleteBtn != null) _agDeleteBtn.gameObject.SetActive(_agIsUser && _agOp == AuthorOps.Update);
            RenderChips(_agToolRows, _tools, _agToolsOff, _agTools, "agtool:");
            RenderChips(_agSkillRows, SkillNameList(), _agSkillsOff, _agSkills, "agskill:");
        }

        private void RenderChips(List<ChipRef> rows, List<string> items, int offset, HashSet<string> selected, string prefix)
        {
            int max = Mathf.Max(0, items.Count - rows.Count);
            offset = Mathf.Clamp(offset, 0, max);
            for (int i = 0; i < rows.Count; i++)
            {
                int idx = offset + i;
                var chip = rows[i];
                if (idx < items.Count)
                {
                    string id = items[idx];
                    bool on = selected.Contains(id);
                    chip.Btn.gameObject.SetActive(true);
                    chip.Text.text = (on ? "\u2611 " : "\u2610 ") + id;
                    if (chip.Mat != null) HoloMaterials.SetAlbedo(chip.Mat.material, on ? new Color(0.2f, 0.5f, 0.4f) : new Color(0.18f, 0.2f, 0.28f));
                    _buttons[chip.Btn] = prefix + id;
                }
                else { chip.Btn.gameObject.SetActive(false); _buttons[chip.Btn] = ""; }
            }
        }

        // ---- construction -------------------------------------------------------------------

        private void BuildUI()
        {
            _root = new GameObject("StudioRoot");
            _root.transform.SetParent(transform, false);
            var bb = gameObject.AddComponent<Billboard>();
            bb.yawOnly = false;

            BuildMainPanel();
            BuildSkillPanel();
            BuildAgentPanel();
        }

        private void BuildMainPanel()
        {
            _mainPanel = Panel("Main");
            Quad(_mainPanel, "bg", new Vector3(0, 0, 0.01f), new Vector3(0.86f, 0.62f, 0.008f), new Color(0.06f, 0.07f, 0.11f, 0.96f));
            Label(_mainPanel, "title", "Studio \u00B7 Agents & Skills", 0.036f, new Color(0.7f, 0.85f, 1f), new Vector3(0, 0.26f, -0.006f), new Vector2(0.8f, 0.05f));

            Label(_mainPanel, "ah", "Agents", 0.03f, new Color(0.7f, 0.8f, 1f), new Vector3(-0.21f, 0.2f, -0.006f), new Vector2(0.3f, 0.04f));
            Label(_mainPanel, "sh", "Skills", 0.03f, new Color(0.7f, 0.8f, 1f), new Vector3(0.21f, 0.2f, -0.006f), new Vector2(0.3f, 0.04f));

            float top = 0.14f, rh = 0.05f;
            for (int i = 0; i < ListRows; i++)
            {
                _agentRows.Add(ListRow(_mainPanel, $"arow{i}", new Vector3(-0.21f, top - i * rh, -0.006f)));
                _skillRows.Add(ListRow(_mainPanel, $"srow{i}", new Vector3(0.21f, top - i * rh, -0.006f)));
            }

            Button(_mainPanel, "agents_up", "\u2191", new Vector3(-0.02f, 0.14f, -0.006f), new Vector3(0.04f, 0.04f, 0.012f), new Color(0.22f, 0.26f, 0.36f));
            Button(_mainPanel, "agents_down", "\u2193", new Vector3(-0.02f, 0.09f, -0.006f), new Vector3(0.04f, 0.04f, 0.012f), new Color(0.22f, 0.26f, 0.36f));
            Button(_mainPanel, "skills_up", "\u2191", new Vector3(0.4f, 0.14f, -0.006f), new Vector3(0.04f, 0.04f, 0.012f), new Color(0.22f, 0.26f, 0.36f));
            Button(_mainPanel, "skills_down", "\u2193", new Vector3(0.4f, 0.09f, -0.006f), new Vector3(0.04f, 0.04f, 0.012f), new Color(0.22f, 0.26f, 0.36f));

            Button(_mainPanel, "new_agent", "+ Agent", new Vector3(-0.21f, -0.2f, -0.006f), new Vector3(0.22f, 0.055f, 0.014f), new Color(0.22f, 0.45f, 0.4f));
            Button(_mainPanel, "new_skill", "+ Skill", new Vector3(0.21f, -0.2f, -0.006f), new Vector3(0.22f, 0.055f, 0.014f), new Color(0.22f, 0.45f, 0.4f));
            Button(_mainPanel, "close", "Close", new Vector3(0.36f, -0.27f, -0.006f), new Vector3(0.16f, 0.05f, 0.014f), new Color(0.4f, 0.3f, 0.35f));
            _mainStatus = Label(_mainPanel, "status", "", 0.022f, new Color(0.7f, 0.85f, 1f), new Vector3(-0.06f, -0.27f, -0.006f), new Vector2(0.5f, 0.04f), TextAlignmentOptions.Left);
        }

        private void BuildSkillPanel()
        {
            _skillPanel = Panel("SkillEditor");
            Quad(_skillPanel, "bg", new Vector3(0, 0, 0.01f), new Vector3(0.86f, 0.62f, 0.008f), new Color(0.06f, 0.08f, 0.1f, 0.96f));
            _skHeader = Label(_skillPanel, "h", "New Skill", 0.034f, new Color(0.7f, 0.85f, 1f), new Vector3(0, 0.26f, -0.006f), new Vector2(0.8f, 0.05f));

            _skNameV = Field(_skillPanel, "Name", "sk_name", new Vector3(0, 0.19f, -0.006f), true);
            _skCatV = FieldCycle(_skillPanel, "Category", "sk_cat_prev", "sk_cat_next", new Vector3(0, 0.13f, -0.006f));
            _skAgentV = FieldCycle(_skillPanel, "Owner", "sk_agent_prev", "sk_agent_next", new Vector3(0, 0.07f, -0.006f));
            _skDescV = Field(_skillPanel, "Desc", "sk_desc", new Vector3(0, 0.01f, -0.006f), true);
            _skBodyV = Field(_skillPanel, "Body", "sk_body", new Vector3(0, -0.05f, -0.006f), true);

            Label(_skillPanel, "toolsh", "Allowed tools", 0.024f, new Color(0.7f, 0.8f, 0.95f), new Vector3(0.28f, 0.19f, -0.006f), new Vector2(0.26f, 0.04f));
            float ctop = 0.13f, crh = 0.045f;
            for (int i = 0; i < ChipRows; i++)
                _skToolRows.Add(Chip(_skillPanel, $"sktoolrow{i}", new Vector3(0.28f, ctop - i * crh, -0.006f)));
            Button(_skillPanel, "sk_tools_up", "\u2191", new Vector3(0.41f, 0.13f, -0.006f), new Vector3(0.04f, 0.04f, 0.012f), new Color(0.22f, 0.26f, 0.36f));
            Button(_skillPanel, "sk_tools_down", "\u2193", new Vector3(0.41f, -0.06f, -0.006f), new Vector3(0.04f, 0.04f, 0.012f), new Color(0.22f, 0.26f, 0.36f));

            Button(_skillPanel, "sk_save", "Save", new Vector3(-0.28f, -0.22f, -0.006f), new Vector3(0.18f, 0.055f, 0.014f), new Color(0.2f, 0.55f, 0.4f));
            _skDeleteBtn = Button(_skillPanel, "sk_delete", "Delete", new Vector3(-0.08f, -0.22f, -0.006f), new Vector3(0.18f, 0.055f, 0.014f), new Color(0.6f, 0.28f, 0.28f));
            Button(_skillPanel, "sk_cancel", "Cancel", new Vector3(0.12f, -0.22f, -0.006f), new Vector3(0.18f, 0.055f, 0.014f), new Color(0.35f, 0.32f, 0.4f));
            _skStatus = Label(_skillPanel, "status", "", 0.022f, new Color(0.7f, 0.85f, 1f), new Vector3(0, -0.28f, -0.006f), new Vector2(0.8f, 0.04f));
        }

        private void BuildAgentPanel()
        {
            _agentPanel = Panel("AgentEditor");
            Quad(_agentPanel, "bg", new Vector3(0, 0, 0.01f), new Vector3(0.86f, 0.62f, 0.008f), new Color(0.07f, 0.07f, 0.11f, 0.96f));
            _agHeader = Label(_agentPanel, "h", "New Agent", 0.034f, new Color(0.7f, 0.85f, 1f), new Vector3(0, 0.26f, -0.006f), new Vector2(0.8f, 0.05f));

            _agRoleV = Field(_agentPanel, "Role id", "ag_role", new Vector3(0, 0.19f, -0.006f), true);
            _agNameV = Field(_agentPanel, "Name", "ag_name", new Vector3(0, 0.13f, -0.006f), true);
            _agPersonaV = Field(_agentPanel, "Persona", "ag_persona", new Vector3(0, 0.07f, -0.006f), true);

            Label(_agentPanel, "toolsh", "Tools", 0.024f, new Color(0.7f, 0.8f, 0.95f), new Vector3(-0.24f, 0.0f, -0.006f), new Vector2(0.2f, 0.04f));
            Label(_agentPanel, "skillsh", "Skills", 0.024f, new Color(0.7f, 0.8f, 0.95f), new Vector3(0.18f, 0.0f, -0.006f), new Vector2(0.2f, 0.04f));
            float ctop = -0.05f, crh = 0.045f;
            for (int i = 0; i < ChipRows; i++)
            {
                _agToolRows.Add(Chip(_agentPanel, $"agtoolrow{i}", new Vector3(-0.24f, ctop - i * crh, -0.006f)));
                _agSkillRows.Add(Chip(_agentPanel, $"agskillrow{i}", new Vector3(0.18f, ctop - i * crh, -0.006f)));
            }
            Button(_agentPanel, "ag_tools_up", "\u2191", new Vector3(-0.05f, -0.05f, -0.006f), new Vector3(0.04f, 0.04f, 0.012f), new Color(0.22f, 0.26f, 0.36f));
            Button(_agentPanel, "ag_tools_down", "\u2193", new Vector3(-0.05f, -0.2f, -0.006f), new Vector3(0.04f, 0.04f, 0.012f), new Color(0.22f, 0.26f, 0.36f));
            Button(_agentPanel, "ag_skills_up", "\u2191", new Vector3(0.39f, -0.05f, -0.006f), new Vector3(0.04f, 0.04f, 0.012f), new Color(0.22f, 0.26f, 0.36f));
            Button(_agentPanel, "ag_skills_down", "\u2193", new Vector3(0.39f, -0.2f, -0.006f), new Vector3(0.04f, 0.04f, 0.012f), new Color(0.22f, 0.26f, 0.36f));

            Button(_agentPanel, "ag_save", "Save", new Vector3(-0.28f, -0.26f, -0.006f), new Vector3(0.18f, 0.05f, 0.014f), new Color(0.2f, 0.55f, 0.4f));
            _agDeleteBtn = Button(_agentPanel, "ag_delete", "Delete", new Vector3(-0.08f, -0.26f, -0.006f), new Vector3(0.18f, 0.05f, 0.014f), new Color(0.6f, 0.28f, 0.28f));
            Button(_agentPanel, "ag_cancel", "Cancel", new Vector3(0.12f, -0.26f, -0.006f), new Vector3(0.18f, 0.05f, 0.014f), new Color(0.35f, 0.32f, 0.4f));
            _agStatus = Label(_agentPanel, "status", "", 0.022f, new Color(0.7f, 0.85f, 1f), new Vector3(0.34f, -0.26f, -0.006f), new Vector2(0.3f, 0.04f), TextAlignmentOptions.Left);
        }

        // value field: label + tappable value (opens keyboard) + ✎
        private TextMeshPro Field(GameObject panel, string label, string element, Vector3 pos, bool editable)
        {
            Label(panel, $"l_{element}", label, 0.022f, new Color(0.65f, 0.72f, 0.85f), pos + new Vector3(-0.36f, 0, 0), new Vector2(0.16f, 0.04f), TextAlignmentOptions.Left);
            var v = Label(panel, $"v_{element}", "", 0.024f, Color.white, pos + new Vector3(-0.06f, 0, 0), new Vector2(0.36f, 0.04f), TextAlignmentOptions.Left);
            if (editable) Button(panel, element, "\u270E", pos + new Vector3(0.22f, 0, 0), new Vector3(0.045f, 0.04f, 0.012f), new Color(0.25f, 0.3f, 0.42f));
            return v;
        }

        private TextMeshPro FieldCycle(GameObject panel, string label, string prevEl, string nextEl, Vector3 pos)
        {
            Label(panel, $"l_{prevEl}", label, 0.022f, new Color(0.65f, 0.72f, 0.85f), pos + new Vector3(-0.36f, 0, 0), new Vector2(0.16f, 0.04f), TextAlignmentOptions.Left);
            var v = Label(panel, $"v_{prevEl}", "", 0.024f, Color.white, pos + new Vector3(-0.06f, 0, 0), new Vector2(0.3f, 0.04f), TextAlignmentOptions.Left);
            Button(panel, prevEl, "\u2039", pos + new Vector3(0.18f, 0, 0), new Vector3(0.04f, 0.04f, 0.012f), new Color(0.2f, 0.28f, 0.42f));
            Button(panel, nextEl, "\u203A", pos + new Vector3(0.23f, 0, 0), new Vector3(0.04f, 0.04f, 0.012f), new Color(0.2f, 0.28f, 0.42f));
            return v;
        }

        private RowRef ListRow(GameObject panel, string name, Vector3 pos)
        {
            var btn = MakeCube(panel.transform, name, pos, new Vector3(0.34f, 0.045f, 0.012f), new Color(0.13f, 0.16f, 0.24f), true);
            _buttons[btn] = "";
            var txt = Label(panel, $"t_{name}", "", 0.02f, Color.white, pos + new Vector3(0, 0, -0.012f), new Vector2(0.32f, 0.04f), TextAlignmentOptions.Left);
            return new RowRef { Btn = btn, Text = txt };
        }

        private ChipRef Chip(GameObject panel, string name, Vector3 pos)
        {
            var btn = MakeCube(panel.transform, name, pos, new Vector3(0.24f, 0.04f, 0.012f), new Color(0.18f, 0.2f, 0.28f), true);
            _buttons[btn] = "";
            var txt = Label(panel, $"t_{name}", "", 0.018f, Color.white, pos + new Vector3(0, 0, -0.012f), new Vector2(0.22f, 0.038f), TextAlignmentOptions.Left);
            return new ChipRef { Btn = btn, Mat = btn.GetComponent<Renderer>(), Text = txt };
        }

        private GameObject Panel(string name)
        {
            var go = new GameObject(name);
            go.transform.SetParent(_root.transform, false);
            return go;
        }

        private void Quad(GameObject panel, string name, Vector3 pos, Vector3 scale, Color color)
            => MakeCube(panel.transform, name, pos, scale, color, false);

        private TextMeshPro Label(GameObject panel, string name, string text, float size, Color color, Vector3 pos, Vector2 rect,
            TextAlignmentOptions align = TextAlignmentOptions.Center)
        {
            var go = new GameObject(name);
            go.transform.SetParent(panel.transform, false);
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

        private Transform Button(GameObject panel, string element, string label, Vector3 pos, Vector3 scale, Color color)
        {
            var btn = MakeCube(panel.transform, $"btn_{element}", pos, scale, color, true);
            _buttons[btn] = element;
            Label(panel, $"lbl_{element}", label, Mathf.Min(0.022f, scale.y * 0.5f), Color.white, pos + new Vector3(0, 0, -scale.z), new Vector2(scale.x, scale.y));
            return btn;
        }

        private Transform MakeCube(Transform parent, string name, Vector3 pos, Vector3 scale, Color color, bool keepCollider)
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

        private void Update()
        {
            if (!IsVisible) return;
#if ENABLE_LEGACY_INPUT_MANAGER
            if (Input.GetMouseButtonDown(0)) TryClick();
#endif
        }

#if ENABLE_LEGACY_INPUT_MANAGER
        private void TryClick()
        {
            var cam = Camera.main;
            if (cam == null) return;
            if (!Physics.Raycast(cam.ScreenPointToRay(Input.mousePosition), out var hit, 20f)) return;
            if (_buttons.TryGetValue(hit.collider.transform, out var element) && !string.IsNullOrEmpty(element)) Press(element);
        }
#endif

        // ---- helpers ------------------------------------------------------------------------

        private List<string> AgentRoleList()
        {
            var list = new List<string>();
            foreach (var a in _agents) list.Add(a.Role);
            return list;
        }

        private List<string> SkillNameList()
        {
            var list = new List<string>();
            foreach (var s in _skills) list.Add(s.Name);
            return list;
        }

        private static string FirstOr(List<string> list, string fallback) => (list != null && list.Count > 0) ? list[0] : fallback;

        internal static string Cycle(List<string> list, string current, int dir)
        {
            if (list == null || list.Count == 0) return current;
            int idx = Mathf.Max(0, list.IndexOf(current));
            idx = ((idx + dir) % list.Count + list.Count) % list.Count;
            return list[idx];
        }

        private static void SetStatus(TextMeshPro t, string text, bool error)
        {
            if (t == null) return;
            t.text = text;
            t.color = error ? new Color(1f, 0.45f, 0.4f) : new Color(0.7f, 0.85f, 1f);
        }

        private static string Badge(string source)
            => source == AuthoringSources.User ? "<color=#7fd6a0>[user]</color>" : "<color=#8899aa>[builtin]</color>";

        private static string Truncate(string s, int n) => string.IsNullOrEmpty(s) || s.Length <= n ? s : s.Substring(0, n) + "\u2026";

        // agentskills.io name rules: lowercase, [a-z0-9-].
        internal static string Sanitize(string s)
        {
            if (string.IsNullOrEmpty(s)) return "";
            var sb = new StringBuilder();
            foreach (char c in s.Trim().ToLowerInvariant())
            {
                if ((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '-') sb.Append(c);
                else if (c == ' ' || c == '_') sb.Append('-');
            }
            return sb.ToString();
        }

        private static string Prettify(string role)
        {
            if (string.IsNullOrEmpty(role)) return "Agent";
            var sb = new StringBuilder();
            foreach (var part in role.Split('-'))
            {
                if (part.Length == 0 || part == "agent") continue;
                sb.Append(char.ToUpperInvariant(part[0]));
                if (part.Length > 1) sb.Append(part.Substring(1));
                sb.Append(' ');
            }
            var t = sb.ToString().Trim();
            return t.Length == 0 ? role : t;
        }
    }
}
