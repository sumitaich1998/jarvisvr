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
    public class JarvisPresencePlayTests
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

        private static void AssertColor(Color expected, Color actual, float tol = 0.01f)
        {
            Assert.AreEqual(expected.r, actual.r, tol, "r");
            Assert.AreEqual(expected.g, actual.g, tol, "g");
            Assert.AreEqual(expected.b, actual.b, tol, "b");
        }

        [UnityTest]
        public IEnumerator Thinking_Speech_Map_To_TargetColors()
        {
            var conn = PlayModeTestUtil.NewConnection(_track);
            var presence = PlayModeTestUtil.NewComponent<JarvisPresence>("presence", _track);
            yield return null; // Awake builds orb; OnEnable subscribes

            conn.Router.Route(EnvelopeSerializer.Build(MessageTypes.AgentThinking,
                new AgentThinking { Stage = ThinkingStages.Planning, Label = "Planning…" }, "S"));
            AssertColor(presence.thinkingColor, presence.CurrentTarget);

            conn.Router.Route(EnvelopeSerializer.Build(MessageTypes.AgentThinking,
                new AgentThinking { Stage = ThinkingStages.Perceiving }, "S"));
            AssertColor(presence.perceivingColor, presence.CurrentTarget);

            conn.Router.Route(EnvelopeSerializer.Build(MessageTypes.AgentThinking,
                new AgentThinking { Stage = ThinkingStages.Done }, "S"));
            AssertColor(presence.idleColor, presence.CurrentTarget);

            // streaming (non-final) speech → speaking color
            conn.Router.Route(EnvelopeSerializer.Build(MessageTypes.AgentSpeech,
                new AgentSpeech { Text = "Here's ", Final = false }, "S"));
            AssertColor(presence.speakingColor, presence.CurrentTarget);
            yield return null;
        }

        [UnityTest]
        public IEnumerator Transcript_IsCaptioned()
        {
            var conn = PlayModeTestUtil.NewConnection(_track);
            var presence = PlayModeTestUtil.NewComponent<JarvisPresence>("presence", _track);
            yield return null;

            conn.Router.Route(EnvelopeSerializer.Build(MessageTypes.AgentTranscript,
                new TextPayload("weather in tokyo"), "S"));
            Assert.IsNotNull(presence.CaptionText);
            Assert.IsTrue(presence.CaptionText.Contains("weather in tokyo"));
            yield return null;
        }
    }
}
