using System.Collections.Generic;
using NUnit.Framework;
using Newtonsoft.Json.Linq;
using JarvisVR.Protocol;

namespace JarvisVR.Tests.EditMode
{
    /// <summary>Serialize→deserialize every message payload through the envelope and assert key
    /// fields survive (covers all v1.0–v1.3 DTO classes).</summary>
    public class ProtocolRoundTripTests
    {
        private static T RoundTrip<T>(string type, object payload) where T : class
        {
            string json = EnvelopeSerializer.BuildJson(type, payload, "S");
            var env = EnvelopeSerializer.Deserialize(json);
            Assert.AreEqual(type, env.Type, "type should survive");
            return env.PayloadAs<T>();
        }

        private static void AssertFloats(float[] expected, float[] actual)
        {
            Assert.IsNotNull(actual);
            Assert.AreEqual(expected.Length, actual.Length);
            for (int i = 0; i < expected.Length; i++) Assert.AreEqual(expected[i], actual[i], 1e-4f);
        }

        // ---- handshake ----------------------------------------------------------------------

        [Test]
        public void ClientHello_RoundTrips()
        {
            var hello = new ClientHello { AppVersion = "0.1.0", Locale = "en-US" };
            hello.Capabilities.CameraPassthrough = true;
            hello.Capabilities.EyeTracking = true;
            var p = RoundTrip<ClientHello>(MessageTypes.ClientHello, hello);
            Assert.AreEqual("quest3", p.Device);
            Assert.AreEqual("0.1.0", p.AppVersion);
            Assert.IsTrue(p.Capabilities.CameraPassthrough);
            Assert.IsTrue(p.Capabilities.EyeTracking);
            Assert.IsFalse(p.Capabilities.Depth);
        }

        [Test]
        public void ServerHelloAck_RoundTrips()
        {
            var ack = new ServerHelloAck
            {
                Session = "uuid", ProtocolVersion = "1.3.0",
                Agent = new AgentInfo { Name = "Jarvis", Model = "mock" },
                Tools = new[] { "get_weather", "start_timer" },
                Voice = new VoiceInfo { Tts = true, WakeWord = "jarvis" },
                Orchestration = true, Agents = new[] { "research-agent" }, Tracing = true, Authoring = true,
            };
            var p = RoundTrip<ServerHelloAck>(MessageTypes.ServerHelloAck, ack);
            Assert.AreEqual("uuid", p.Session);
            Assert.AreEqual("Jarvis", p.Agent.Name);
            Assert.AreEqual(2, p.Tools.Length);
            Assert.IsTrue(p.Voice.Tts);
            Assert.IsTrue(p.Orchestration && p.Tracing && p.Authoring);
            Assert.AreEqual("research-agent", p.Agents[0]);
        }

        // ---- user / agent -------------------------------------------------------------------

        [Test]
        public void TextPayload_WithPerceptionFlag_RoundTrips()
        {
            var p = RoundTrip<TextPayload>(MessageTypes.UserText, new TextPayload("hi", 0.5f) { AttachPerception = true });
            Assert.AreEqual("hi", p.Text);
            Assert.AreEqual(0.5f, p.Confidence.Value, 1e-4f);
            Assert.IsTrue(p.AttachPerception.Value);
        }

        [Test]
        public void AgentThinking_WithAttribution_RoundTrips()
        {
            var p = RoundTrip<AgentThinking>(MessageTypes.AgentThinking, new AgentThinking
            { Stage = ThinkingStages.ToolCall, Label = "Calling…", Tool = "get_weather", AgentId = "a1", Role = "research-agent", Skill = "web-research" });
            Assert.AreEqual("tool_call", p.Stage);
            Assert.AreEqual("a1", p.AgentId);
            Assert.AreEqual("web-research", p.Skill);
        }

        [Test]
        public void AgentSpeech_RoundTrips()
        {
            var p = RoundTrip<AgentSpeech>(MessageTypes.AgentSpeech, new AgentSpeech { Text = "Here's Tokyo.", Final = true, Emotion = "neutral" });
            Assert.AreEqual("Here's Tokyo.", p.Text);
            Assert.IsTrue(p.Final);
            Assert.AreEqual("neutral", p.Emotion);
        }

        // ---- holograms ----------------------------------------------------------------------

        [Test]
        public void HologramObject_Spawn_RoundTrips()
        {
            var obj = new HologramObject
            {
                ObjectId = "O1", WidgetType = WidgetTypes.WeatherOrb,
                Transform = new HoloTransform { Anchor = Anchors.Head, Position = new[] { 0.3f, 0f, 0.8f }, Rotation = new[] { 0f, 0f, 0f, 1f }, Scale = new[] { 1f, 1f, 1f }, Billboard = true },
                Props = new JObject { ["city"] = "Tokyo", ["temp_c"] = 18 },
                Interactable = true, Interactions = new[] { "grab", "tap" }, TtlMs = 0,
            };
            var p = RoundTrip<HologramObject>(MessageTypes.HoloSpawn, obj);
            Assert.AreEqual("O1", p.ObjectId);
            Assert.AreEqual(Anchors.Head, p.Transform.Anchor);
            AssertFloats(new[] { 0.3f, 0f, 0.8f }, p.Transform.Position);
            Assert.IsTrue(p.Transform.Billboard.Value);
            Assert.AreEqual("Tokyo", (string)p.Props["city"]);
            Assert.AreEqual(2, p.Interactions.Length);
        }

        [Test]
        public void HoloUpdateDestroyLayout_RoundTrip()
        {
            var u = RoundTrip<HoloUpdate>(MessageTypes.HoloUpdate, new HoloUpdate { ObjectId = "O1", Props = new JObject { ["running"] = false } });
            Assert.AreEqual("O1", u.ObjectId);
            Assert.AreEqual(false, (bool)u.Props["running"]);

            var d = RoundTrip<HoloDestroy>(MessageTypes.HoloDestroy, new HoloDestroy { ObjectId = "O1", FadeMs = 300 });
            Assert.AreEqual(300, d.FadeMs);

            var l = RoundTrip<HoloLayout>(MessageTypes.HoloLayout, new HoloLayout { Arrangement = Arrangements.Arc, Anchor = Anchors.Head, Objects = new List<string> { "a", "b" }, Spacing = 0.25f });
            Assert.AreEqual("arc", l.Arrangement);
            Assert.AreEqual(2, l.Objects.Count);
            Assert.AreEqual(0.25f, l.Spacing, 1e-4f);
        }

        [Test]
        public void ClientInteractionAndScene_RoundTrip()
        {
            var ix = RoundTrip<ClientInteraction>(MessageTypes.ClientInteraction, new ClientInteraction
            { ObjectId = "O1", WidgetType = "timer", Action = InteractionActions.Slider, Element = "seek", Value = new JObject { ["slider"] = 0.4f }, Hand = "right" });
            Assert.AreEqual("slider", ix.Action);
            Assert.AreEqual(0.4f, (float)ix.Value["slider"], 1e-4f);

            var scene = RoundTrip<ClientScene>(MessageTypes.ClientScene, new ClientScene
            {
                Head = new PosePayload { Position = new[] { 0f, 1.6f, 0f }, Rotation = new[] { 0f, 0f, 0f, 1f } },
                Surfaces = new List<Surface> { new Surface { Id = "floor", Type = "floor", Center = new[] { 0f, 0f, 0f }, Normal = new[] { 0f, 1f, 0f } } },
                Anchors = new List<AnchorPose> { new AnchorPose { Id = "uuid", Position = new[] { 1f, 0f, 1f }, Rotation = new[] { 0f, 0f, 0f, 1f } } },
            });
            AssertFloats(new[] { 0f, 1.6f, 0f }, scene.Head.Position);
            Assert.AreEqual("floor", scene.Surfaces[0].Type);
            Assert.AreEqual("uuid", scene.Anchors[0].Id);
        }

        // ---- perception ---------------------------------------------------------------------

        [Test]
        public void Perception_Payloads_RoundTrip()
        {
            var vf = RoundTrip<VisionFrame>(MessageTypes.PerceptionVisionFrame, new VisionFrame
            { FrameId = "F1", Camera = CameraIds.RgbCenter, Format = "jpeg", Width = 1024, Height = 1024, Quality = 70, Transport = VisionTransports.Inline, Data = "abc", Seq = 5, TsCapture = 99, Pose = new PosePayload { Position = new[] { 0f, 1.6f, 0f }, Rotation = new[] { 0f, 0f, 0f, 1f } }, Intrinsics = new CameraIntrinsics { Fx = 720, Fy = 720, Cx = 512, Cy = 512 } });
            Assert.AreEqual("F1", vf.FrameId);
            Assert.AreEqual(1024, vf.Width);
            Assert.AreEqual("abc", vf.Data);
            Assert.AreEqual(720f, vf.Intrinsics.Fx, 1e-3f);

            var ae = RoundTrip<AudioEvent>(MessageTypes.PerceptionAudioEvent, new AudioEvent { Label = "doorbell", Confidence = 0.82f, Ts = 1, LoudnessDb = -22f });
            Assert.AreEqual("doorbell", ae.Label);
            Assert.AreEqual(0.82f, ae.Confidence, 1e-4f);

            var asc = RoundTrip<AudioScene>(MessageTypes.PerceptionAudioScene, new AudioScene { AmbientTranscript = "…", Speaker = "other", Sounds = new List<SoundLabel> { new SoundLabel { Label = "music", Confidence = 0.6f } }, LoudnessDb = -30f, WindowMs = 4000 });
            Assert.AreEqual("other", asc.Speaker);
            Assert.AreEqual("music", asc.Sounds[0].Label);

            var gaze = RoundTrip<GazePayload>(MessageTypes.PerceptionGaze, new GazePayload { Source = GazeSources.Eyes, Origin = new[] { 0f, 1.6f, 0f }, Direction = new[] { 0f, 0f, 1f }, HitObjectId = "O9", HitPoint = new[] { 0.2f, 1.3f, 0.9f }, DwellMs = 600 });
            Assert.AreEqual("eyes", gaze.Source);
            Assert.AreEqual("O9", gaze.HitObjectId);
            Assert.AreEqual(600, gaze.DwellMs);

            var so = RoundTrip<SceneObjects>(MessageTypes.PerceptionSceneObjects, new SceneObjects { FrameId = "F1", Objects = new List<DetectedObject> { new DetectedObject { Label = "mug", Confidence = 0.78f, Bbox = new[] { 1, 2, 3, 4 }, Position = new[] { 0.3f, 0.8f, 0.7f }, Anchor = Anchors.World } } });
            Assert.AreEqual("mug", so.Objects[0].Label);
            CollectionAssert.AreEqual(new[] { 1, 2, 3, 4 }, so.Objects[0].Bbox);

            var st = RoundTrip<PerceptionState>(MessageTypes.PerceptionState, new PerceptionState { Vision = new VisionState { Active = true, Fps = 2, Resolution = "1024x1024", Camera = "rgb_center" }, AmbientAudio = new StreamActive { Active = true }, Gaze = new StreamActive { Active = false }, Thermal = ThermalStates.Nominal, Battery = 0.74f });
            Assert.IsTrue(st.Vision.Active);
            Assert.AreEqual(2f, st.Vision.Fps, 1e-4f);
            Assert.AreEqual(0.74f, st.Battery, 1e-4f);

            var req = RoundTrip<PerceptionRequest>(MessageTypes.PerceptionRequest, new PerceptionRequest { Stream = PerceptionStreams.Vision, Action = PerceptionActions.Start, Fps = 2, MaxResolution = "1024x1024", Quality = 70, DurationMs = 0, Reason = "user asked" });
            Assert.AreEqual("vision", req.Stream);
            Assert.AreEqual(2f, req.Fps.Value, 1e-4f);

            var obs = RoundTrip<AgentObservation>(MessageTypes.AgentObservation, new AgentObservation { Text = "I see a mug", Final = true, Annotations = new List<Annotation> { new Annotation { Label = "mug", ObjectId = "O9", Position = new[] { 0.3f, 0.8f, 0.7f }, Anchor = Anchors.World } } });
            Assert.AreEqual("I see a mug", obs.Text);
            Assert.AreEqual("mug", obs.Annotations[0].Label);
        }

        // ---- settings (§5.15) ---------------------------------------------------------------

        [Test]
        public void Settings_Payloads_RoundTrip()
        {
            var get = RoundTrip<SettingsGet>(MessageTypes.ClientSettingsGet, new SettingsGet(SettingsSections.Llm));
            Assert.AreEqual("llm", get.Section);

            var upd = RoundTrip<ClientSettingsUpdate>(MessageTypes.ClientSettingsUpdate, new ClientSettingsUpdate { Llm = new LlmConfigUpdate { Provider = "openai", Model = "gpt-4o", BaseUrl = null, ApiKey = "sk-secret" } });
            Assert.AreEqual("openai", upd.Llm.Provider);
            Assert.AreEqual("sk-secret", upd.Llm.ApiKey);

            var srv = RoundTrip<ServerSettings>(MessageTypes.ServerSettings, new ServerSettings
            {
                Llm = new LlmSettings
                {
                    Current = new LlmCurrent { Provider = "openai", Model = "gpt-4o", BaseUrl = null, KeySet = true },
                    Providers = new List<ProviderInfo> { new ProviderInfo { Id = "ollama", Name = "Ollama", DefaultModel = "llama3.1", Models = new List<string> { "llama3.1" }, NeedsKey = false, NeedsBaseUrl = true, KeySet = false, Capabilities = new ProviderCapabilities { Tools = true, Vision = false } } },
                },
            });
            Assert.IsTrue(srv.Llm.Current.KeySet);
            Assert.AreEqual("ollama", srv.Llm.Providers[0].Id);
            Assert.IsTrue(srv.Llm.Providers[0].NeedsBaseUrl);
        }

        // ---- orchestration (§9) -------------------------------------------------------------

        [Test]
        public void Orchestration_Payloads_RoundTrip()
        {
            var plan = RoundTrip<OrchestrationPlan>(MessageTypes.OrchestrationPlan, new OrchestrationPlan
            {
                PlanId = "p1", Goal = "weather + timer",
                Agents = new List<PlanAgent>
                {
                    new PlanAgent { AgentId = "jarvis", Role = "orchestrator", Name = "Jarvis", Parent = null, Level = 0 },
                    new PlanAgent { AgentId = "a1", Role = "research-agent", Name = "Research", Parent = "jarvis", Level = 1, Subtask = "weather", Skills = new List<string> { "web-research" } },
                },
                Edges = new List<PlanEdge> { new PlanEdge { From = "jarvis", To = "a1" } },
            });
            Assert.AreEqual("p1", plan.PlanId);
            Assert.AreEqual(2, plan.Agents.Count);
            Assert.AreEqual("jarvis", plan.Edges[0].From);
            Assert.AreEqual("web-research", plan.Agents[1].Skills[0]);

            var status = RoundTrip<AgentStatus>(MessageTypes.OrchestrationAgentStatus, new AgentStatus { PlanId = "p1", AgentId = "a1", Role = "research-agent", Parent = "jarvis", Level = 1, State = AgentStates.Working, Skill = "web-research", Label = "Looking…", Progress = 0.5f });
            Assert.AreEqual("working", status.State);
            Assert.AreEqual(0.5f, status.Progress.Value, 1e-4f);

            var ho = RoundTrip<AgentHandoff>(MessageTypes.OrchestrationHandoff, new AgentHandoff { PlanId = "p1", FromAgent = "a1", ToAgent = "a1.1", ToRole = "summarizer", Level = 2, Subtask = "merge", Reason = "delegate" });
            Assert.AreEqual("a1.1", ho.ToAgent);
            Assert.AreEqual(2, ho.Level);
        }

        // ---- tracing (§10.1) ----------------------------------------------------------------

        [Test]
        public void Trace_Payloads_RoundTrip()
        {
            var sub = RoundTrip<TraceSubscribe>(MessageTypes.ClientTraceSubscribe, new TraceSubscribe(true));
            Assert.IsTrue(sub.Enabled);

            var ev = RoundTrip<AgentTraceEvent>(MessageTypes.OrchestrationTraceEvent, new AgentTraceEvent { PlanId = "p1", Seq = 7, Ts = 123, AgentId = "a1", Role = "research-agent", Parent = "jarvis", Level = 1, Kind = TraceKinds.ToolCall, Label = "get_weather(Tokyo)", Skill = "web-research", Tool = "get_weather", Detail = "redacted", DurationMs = 120 });
            Assert.AreEqual("tool_call", ev.Kind);
            Assert.AreEqual(7, ev.Seq);
            Assert.AreEqual(120, ev.DurationMs.Value);

            var get = RoundTrip<TraceGet>(MessageTypes.ClientTraceGet, new TraceGet("p1"));
            Assert.AreEqual("p1", get.PlanId);

            var srvTrace = RoundTrip<ServerTrace>(MessageTypes.ServerTrace, new ServerTrace { PlanId = "p1", Goal = "g", Agents = new List<TraceAgent> { new TraceAgent { AgentId = "a1", Role = "research-agent", Parent = "jarvis", Level = 1 } }, Entries = new List<AgentTraceEvent> { ev } });
            Assert.AreEqual(1, srvTrace.Agents.Count);
            Assert.AreEqual(1, srvTrace.Entries.Count);

            var inspect = RoundTrip<AgentInspect>(MessageTypes.ClientAgentInspect, new AgentInspect { AgentId = "a1" });
            Assert.AreEqual("a1", inspect.AgentId);

            var info = RoundTrip<ServerAgentInfo>(MessageTypes.ServerAgentInfo, new ServerAgentInfo { Role = "research-agent", Name = "Research", Source = AuthoringSources.Builtin, Persona = "…", Tools = new List<string> { "web_search" }, Skills = new List<AgentInfoSkill> { new AgentInfoSkill { Name = "web-research", Description = "d", Source = "builtin" } }, Memory = new AgentMemory { Summary = "s", Items = 12, Recent = new List<MemoryItem> { new MemoryItem { Ts = 1, Text = "t" } } } });
            Assert.AreEqual("Research", info.Name);
            Assert.AreEqual("web-research", info.Skills[0].Name);
            Assert.AreEqual(12, info.Memory.Items);
            Assert.AreEqual("t", info.Memory.Recent[0].Text);
        }

        // ---- authoring (§10.2) --------------------------------------------------------------

        [Test]
        public void Authoring_Payloads_RoundTrip()
        {
            var list = RoundTrip<ServerAuthoring>(MessageTypes.ServerAuthoring, new ServerAuthoring
            {
                Agents = new List<AuthoringAgent> { new AuthoringAgent { Role = "research-agent", Name = "Research", Source = "builtin", Skills = new List<string> { "web-research" }, Tools = new List<string> { "web_search" } } },
                Skills = new List<AuthoringSkill> { new AuthoringSkill { Name = "web-research", Agent = "research-agent", Category = "research", Source = "user", Description = "d", Body = "# body", AllowedTools = new List<string> { "web_search" } } },
                Categories = new List<string> { "research", "productivity" },
                Tools = new List<string> { "web_search", "start_timer" },
            });
            Assert.AreEqual("research-agent", list.Agents[0].Role);
            Assert.IsFalse(list.Agents[0].IsUser);
            Assert.IsTrue(list.Skills[0].IsUser);
            Assert.AreEqual(2, list.Categories.Count);

            var sk = RoundTrip<AuthorSkill>(MessageTypes.ClientAuthorSkill, new AuthorSkill { Op = AuthorOps.Create, Name = "track-habit", Category = "productivity", Agent = "productivity-agent", Description = "d", Body = "# body", AllowedTools = new List<string> { "take_note" }, License = "MIT" });
            Assert.AreEqual("create", sk.Op);
            Assert.AreEqual("track-habit", sk.Name);
            Assert.AreEqual("take_note", sk.AllowedTools[0]);

            var ag = RoundTrip<AuthorAgent>(MessageTypes.ClientAuthorAgent, new AuthorAgent { Op = AuthorOps.Update, Role = "finance-agent", Name = "Finance", Persona = "p", Tools = new List<string> { "get_stocks" }, Skills = new List<string> { "market-briefing" } });
            Assert.AreEqual("update", ag.Op);
            Assert.AreEqual("finance-agent", ag.Role);
        }

        // ---- misc: barge_in / error / heartbeat ---------------------------------------------

        [Test]
        public void BargeError_And_Heartbeat_RoundTrip()
        {
            var barge = RoundTrip<BargePayload>(MessageTypes.ClientBargeIn, new BargePayload("user_speech"));
            Assert.AreEqual("user_speech", barge.Reason);

            var err = RoundTrip<ErrorPayload>(MessageTypes.ServerError, new ErrorPayload { Code = ErrorCodes.UnknownWidget, Message = "nope", Fatal = false });
            Assert.AreEqual("unknown_widget", err.Code);
            Assert.IsFalse(err.Fatal);

            // empty-payload messages serialize to {}
            string json = EnvelopeSerializer.BuildJson(MessageTypes.ClientHeartbeat, new EmptyPayload(), "S");
            var env = EnvelopeSerializer.Deserialize(json);
            Assert.AreEqual(MessageTypes.ClientHeartbeat, env.Type);
            Assert.AreEqual(0, env.Payload.Count);
        }

        [Test]
        public void OptionalFields_Omitted_DeserializeToDefaults()
        {
            // minimal status with only required-ish fields; optional ones default
            var p = RoundTrip<AgentStatus>(MessageTypes.OrchestrationAgentStatus, new AgentStatus { AgentId = "a1", State = AgentStates.Queued });
            Assert.AreEqual("a1", p.AgentId);
            Assert.IsFalse(p.Progress.HasValue, "omitted progress stays null");
            Assert.IsNull(p.Skill);
        }
    }
}
