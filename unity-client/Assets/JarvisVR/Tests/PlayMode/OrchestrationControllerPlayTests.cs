using System.Collections;
using System.Collections.Generic;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;
using JarvisVR.Net;
using JarvisVR.Protocol;
using JarvisVR.Shell;

namespace JarvisVR.Tests.PlayMode
{
    public class OrchestrationControllerPlayTests
    {
        private readonly List<Object> _track = new List<Object>();

        [SetUp]
        public void SetUp() => LogAssert.ignoreFailingMessages = true;

        [TearDown]
        public void TearDown()
        {
            PlayModeTestUtil.Cleanup(_track);
            LogAssert.ignoreFailingMessages = false;
        }

        private static OrchestrationPlan SamplePlan() => new OrchestrationPlan
        {
            PlanId = "p1",
            Goal = "weather + timer",
            Agents = new List<PlanAgent>
            {
                new PlanAgent { AgentId = "jarvis", Role = "orchestrator", Name = "Jarvis", Parent = null, Level = 0 },
                new PlanAgent { AgentId = "a1", Role = "research-agent", Name = "Research", Parent = "jarvis", Level = 1 },
                new PlanAgent { AgentId = "a2", Role = "productivity-agent", Name = "Productivity", Parent = "jarvis", Level = 1 },
            },
            Edges = new List<PlanEdge>
            {
                new PlanEdge { From = "jarvis", To = "a1" },
                new PlanEdge { From = "jarvis", To = "a2" },
            },
        };

        [UnityTest]
        public IEnumerator Plan_BuildsNodesAndEdges()
        {
            var conn = PlayModeTestUtil.NewConnection(_track);
            var ctrl = PlayModeTestUtil.NewComponent<OrchestrationController>("orch", _track);
            yield return null;

            conn.Router.Route(EnvelopeSerializer.Build(MessageTypes.OrchestrationPlan, SamplePlan(), "S"));

            Assert.AreEqual(3, ctrl.NodeCount);
            Assert.AreEqual(2, ctrl.EdgeCount);
            Assert.IsTrue(ctrl.HasNode("jarvis"));
            Assert.IsTrue(ctrl.HasNode("a1"));
            Assert.IsTrue(ctrl.HasNode("a2"));
            Assert.IsTrue(ctrl.IsVisible, "a plan shows the team board");
            yield return null;
        }

        [UnityTest]
        public IEnumerator AgentStatus_UpdatesNodeState()
        {
            var conn = PlayModeTestUtil.NewConnection(_track);
            var ctrl = PlayModeTestUtil.NewComponent<OrchestrationController>("orch", _track);
            yield return null;
            conn.Router.Route(EnvelopeSerializer.Build(MessageTypes.OrchestrationPlan, SamplePlan(), "S"));

            conn.Router.Route(EnvelopeSerializer.Build(MessageTypes.OrchestrationAgentStatus,
                new AgentStatus { PlanId = "p1", AgentId = "a1", Role = "research-agent", State = AgentStates.Working, Skill = "web-research", Progress = 0.5f }, "S"));
            Assert.AreEqual(AgentStates.Working, ctrl.NodeState("a1"));

            conn.Router.Route(EnvelopeSerializer.Build(MessageTypes.OrchestrationAgentStatus,
                new AgentStatus { PlanId = "p1", AgentId = "a1", Role = "research-agent", State = AgentStates.Done }, "S"));
            Assert.AreEqual(AgentStates.Done, ctrl.NodeState("a1"));
            yield return null;
        }

        [UnityTest]
        public IEnumerator Handoff_AddsSubAgentAndEdge()
        {
            var conn = PlayModeTestUtil.NewConnection(_track);
            var ctrl = PlayModeTestUtil.NewComponent<OrchestrationController>("orch", _track);
            yield return null;
            conn.Router.Route(EnvelopeSerializer.Build(MessageTypes.OrchestrationPlan, SamplePlan(), "S"));

            conn.Router.Route(EnvelopeSerializer.Build(MessageTypes.OrchestrationHandoff,
                new AgentHandoff { PlanId = "p1", FromAgent = "a1", ToAgent = "a1.1", ToRole = "summarizer", Level = 2 }, "S"));

            Assert.IsTrue(ctrl.HasNode("a1.1"), "handoff adds the sub-agent node");
            Assert.AreEqual(4, ctrl.NodeCount);
            Assert.AreEqual(3, ctrl.EdgeCount, "handoff draws the delegation edge");
            yield return null;
        }

        [UnityTest]
        public IEnumerator TraceEvent_IsBuffered()
        {
            var conn = PlayModeTestUtil.NewConnection(_track);
            var ctrl = PlayModeTestUtil.NewComponent<OrchestrationController>("orch", _track);
            yield return null;
            conn.Router.Route(EnvelopeSerializer.Build(MessageTypes.OrchestrationPlan, SamplePlan(), "S"));

            conn.Router.Route(EnvelopeSerializer.Build(MessageTypes.OrchestrationTraceEvent,
                new AgentTraceEvent { PlanId = "p1", AgentId = "a1", Kind = TraceKinds.ToolCall, Label = "get_weather", Tool = "get_weather", DurationMs = 120 }, "S"));
            conn.Router.Route(EnvelopeSerializer.Build(MessageTypes.OrchestrationTraceEvent,
                new AgentTraceEvent { PlanId = "p1", AgentId = "a1", Kind = TraceKinds.ToolResult, Label = "18°C" }, "S"));

            Assert.AreEqual(2, ctrl.TraceCountFor("a1"));
            Assert.AreEqual(0, ctrl.TraceCountFor("a2"));
            yield return null;
        }
    }
}
