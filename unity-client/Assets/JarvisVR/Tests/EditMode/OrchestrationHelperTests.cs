using NUnit.Framework;
using UnityEngine;
using JarvisVR.Protocol;
using JarvisVR.Shell;

namespace JarvisVR.Tests.EditMode
{
    /// <summary>Tests OrchestrationController's pure mapping helpers (state→color, trace kind→icon
    /// code/color, role→display name, active-state predicate).</summary>
    public class OrchestrationHelperTests
    {
        private static void AssertColor(Color expected, Color actual, float tol = 0.01f)
        {
            Assert.AreEqual(expected.r, actual.r, tol, "r");
            Assert.AreEqual(expected.g, actual.g, tol, "g");
            Assert.AreEqual(expected.b, actual.b, tol, "b");
        }

        [Test]
        public void StateColor_KnownStates()
        {
            AssertColor(new Color(0.2f, 0.65f, 1f), OrchestrationController.StateColor(AgentStates.Working, false));
            AssertColor(new Color(0.3f, 0.85f, 0.45f), OrchestrationController.StateColor(AgentStates.Done, false));
            AssertColor(new Color(0.9f, 0.32f, 0.3f), OrchestrationController.StateColor(AgentStates.Failed, false));
            AssertColor(new Color(0.35f, 0.37f, 0.43f), OrchestrationController.StateColor(AgentStates.Queued, false));
        }

        [Test]
        public void StateColor_UnknownState_RootIsGold_NonRootIsGrey()
        {
            AssertColor(new Color(1f, 0.78f, 0.3f), OrchestrationController.StateColor("???", true));
            AssertColor(new Color(0.4f, 0.45f, 0.55f), OrchestrationController.StateColor("???", false));
        }

        [Test]
        public void KindCode_MapsEachKind()
        {
            Assert.AreEqual("mem", OrchestrationController.KindCode(TraceKinds.MemoryRead));
            Assert.AreEqual("mem+", OrchestrationController.KindCode(TraceKinds.MemoryWrite));
            Assert.AreEqual("skill", OrchestrationController.KindCode(TraceKinds.SkillActivated));
            Assert.AreEqual("tool", OrchestrationController.KindCode(TraceKinds.ToolCall));
            Assert.AreEqual("\u2713", OrchestrationController.KindCode(TraceKinds.ToolResult));
            Assert.AreEqual("obs", OrchestrationController.KindCode(TraceKinds.Observation));
            Assert.AreEqual("deleg", OrchestrationController.KindCode(TraceKinds.Delegated));
            Assert.AreEqual("say", OrchestrationController.KindCode(TraceKinds.Speech));
            Assert.AreEqual("err", OrchestrationController.KindCode(TraceKinds.Error));
        }

        [Test]
        public void KindCode_Unknown_ReturnsRaw()
        {
            Assert.AreEqual("weird", OrchestrationController.KindCode("weird"));
        }

        [Test]
        public void KindColor_ErrorIsRed_ResultIsGreen()
        {
            var err = OrchestrationController.KindColor(TraceKinds.Error);
            Assert.Greater(err.r, err.g);
            Assert.Greater(err.r, err.b);
            var res = OrchestrationController.KindColor(TraceKinds.ToolResult);
            Assert.Greater(res.g, res.r);
        }

        [Test]
        public void Prettify_RoleDisplayNames()
        {
            Assert.AreEqual("Research", OrchestrationController.Prettify("research-agent"));
            Assert.AreEqual("Smart Home", OrchestrationController.Prettify("smart-home-agent"));
            Assert.AreEqual("Jarvis", OrchestrationController.Prettify("orchestrator"));
            Assert.AreEqual("Jarvis", OrchestrationController.Prettify("jarvis"));
            Assert.AreEqual("Agent", OrchestrationController.Prettify(null));
        }

        [Test]
        public void IsActiveState_TrueOnlyForBusyStates()
        {
            Assert.IsTrue(OrchestrationController.IsActiveState(AgentStates.Working));
            Assert.IsTrue(OrchestrationController.IsActiveState(AgentStates.Planning));
            Assert.IsTrue(OrchestrationController.IsActiveState(AgentStates.Delegating));
            Assert.IsFalse(OrchestrationController.IsActiveState(AgentStates.Queued));
            Assert.IsFalse(OrchestrationController.IsActiveState(AgentStates.Waiting));
            Assert.IsFalse(OrchestrationController.IsActiveState(AgentStates.Done));
            Assert.IsFalse(OrchestrationController.IsActiveState(AgentStates.Failed));
        }
    }
}
