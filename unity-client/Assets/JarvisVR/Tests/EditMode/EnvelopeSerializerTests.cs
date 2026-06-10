using NUnit.Framework;
using Newtonsoft.Json.Linq;
using JarvisVR.Protocol;

namespace JarvisVR.Tests.EditMode
{
    public class EnvelopeSerializerTests
    {
        [Test]
        public void Build_SetsVersionTypeAndAutoFields()
        {
            var env = EnvelopeSerializer.Build(MessageTypes.UserText, new TextPayload("hi"), "S1");
            Assert.AreEqual(ProtocolConstants.Version, env.V);
            Assert.AreEqual(MessageTypes.UserText, env.Type);
            Assert.AreEqual("S1", env.Session);
            Assert.IsFalse(string.IsNullOrEmpty(env.Id), "id should be auto-generated");
            Assert.Greater(env.Ts, 0L, "ts should be a positive epoch ms");
            Assert.IsNotNull(env.Payload);
        }

        [Test]
        public void Build_ExplicitIdAndReplyTo_ArePreserved()
        {
            var env = EnvelopeSerializer.Build(MessageTypes.ClientAck, new EmptyPayload(), "S", id: "fixed-id", replyTo: "b3");
            Assert.AreEqual("fixed-id", env.Id);
            Assert.AreEqual("b3", env.ReplyTo);
        }

        [Test]
        public void Build_NullPayload_YieldsEmptyObject()
        {
            var env = EnvelopeSerializer.Build(MessageTypes.ClientHeartbeat, null, "S");
            Assert.IsNotNull(env.Payload);
            Assert.AreEqual(0, env.Payload.Count);
        }

        [Test]
        public void Serialize_OmitsNullSessionAndReplyTo()
        {
            // first client.hello has no session yet, and no reply_to
            string json = EnvelopeSerializer.BuildJson(MessageTypes.ClientHello, new ClientHello(), null);
            Assert.IsFalse(json.Contains("\"session\""), "null session must be omitted");
            Assert.IsFalse(json.Contains("\"reply_to\""), "null reply_to must be omitted");
            Assert.IsTrue(json.Contains("\"type\":\"client.hello\""));
        }

        [Test]
        public void RoundTrip_PreservesEnvelopeAndTypedPayload()
        {
            string json = EnvelopeSerializer.BuildJson(MessageTypes.UserVoiceTranscript,
                new TextPayload("weather in tokyo", 0.97f), "SESSION", id: "a1");
            var env = EnvelopeSerializer.Deserialize(json);

            Assert.AreEqual("a1", env.Id);
            Assert.AreEqual(MessageTypes.UserVoiceTranscript, env.Type);
            Assert.AreEqual("SESSION", env.Session);

            var p = env.PayloadAs<TextPayload>();
            Assert.AreEqual("weather in tokyo", p.Text);
            Assert.AreEqual(0.97f, p.Confidence.Value, 1e-4f);
        }

        [Test]
        public void TryDeserialize_ValidJson_ReturnsTrue()
        {
            string json = EnvelopeSerializer.BuildJson(MessageTypes.AgentSpeech, new AgentSpeech { Text = "hi" }, "S");
            bool ok = EnvelopeSerializer.TryDeserialize(json, out var env, out var error);
            Assert.IsTrue(ok);
            Assert.IsNull(error);
            Assert.AreEqual(MessageTypes.AgentSpeech, env.Type);
        }

        [Test]
        public void TryDeserialize_Garbage_ReturnsFalseWithError()
        {
            bool ok = EnvelopeSerializer.TryDeserialize("{ not json", out var env, out var error);
            Assert.IsFalse(ok);
            Assert.IsNull(env);
            Assert.IsFalse(string.IsNullOrEmpty(error));
        }

        [Test]
        public void TryDeserialize_MissingType_ReturnsFalse()
        {
            // valid JSON object but no "type" → invalid per the envelope contract
            bool ok = EnvelopeSerializer.TryDeserialize("{\"v\":\"1.3.0\",\"payload\":{}}", out _, out var error);
            Assert.IsFalse(ok);
            Assert.AreEqual("missing type", error);
        }

        [Test]
        public void Deserialize_IgnoresUnknownEnvelopeAndPayloadKeys()
        {
            // forward-compatibility: extra keys must not throw (MissingMemberHandling.Ignore)
            string json = "{\"v\":\"9.9.9\",\"id\":\"x\",\"type\":\"agent.speech\",\"ts\":1," +
                          "\"session\":\"S\",\"future_field\":42,\"payload\":{\"text\":\"hello\",\"unknown\":true}}";
            var env = EnvelopeSerializer.Deserialize(json);
            Assert.AreEqual("agent.speech", env.Type);
            Assert.AreEqual("hello", env.PayloadAs<AgentSpeech>().Text);
        }

        [Test]
        public void PayloadAs_PreservesRawJObject()
        {
            var env = EnvelopeSerializer.Build(MessageTypes.HoloSpawn, new HologramObject
            {
                ObjectId = "O1",
                WidgetType = WidgetTypes.WeatherOrb,
                Props = new JObject { ["city"] = "Tokyo", ["temp_c"] = 18 },
            }, "S");

            var obj = env.PayloadAs<HologramObject>();
            Assert.AreEqual("O1", obj.ObjectId);
            Assert.AreEqual("weather_orb", obj.WidgetType);
            Assert.AreEqual("Tokyo", (string)obj.Props["city"]);
            Assert.AreEqual(18, (int)obj.Props["temp_c"]);
        }
    }
}
