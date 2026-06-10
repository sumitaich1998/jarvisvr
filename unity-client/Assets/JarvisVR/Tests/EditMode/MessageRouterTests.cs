using NUnit.Framework;
using JarvisVR.Protocol;

namespace JarvisVR.Tests.EditMode
{
    public class MessageRouterTests
    {
        private MessageRouter _router;

        [SetUp]
        public void SetUp() => _router = new MessageRouter();

        private static Envelope Env(string type) => new Envelope { Type = type, Id = "x", Payload = new Newtonsoft.Json.Linq.JObject() };

        [Test]
        public void On_Route_InvokesHandlerWithEnvelope()
        {
            Envelope received = null;
            _router.On(MessageTypes.AgentSpeech, e => received = e);
            var env = Env(MessageTypes.AgentSpeech);

            _router.Route(env);

            Assert.AreSame(env, received);
        }

        [Test]
        public void Route_UnknownType_FiresOnUnhandledNotHandlers()
        {
            bool handlerCalled = false;
            string unhandledType = null;
            _router.On(MessageTypes.AgentSpeech, _ => handlerCalled = true);
            _router.OnUnhandled += (type, _) => unhandledType = type;

            _router.Route(Env("some.unknown.type"));

            Assert.IsFalse(handlerCalled);
            Assert.AreEqual("some.unknown.type", unhandledType);
        }

        [Test]
        public void Route_FiresOnAnyForEveryMessage()
        {
            int anyCount = 0;
            _router.OnAny += _ => anyCount++;
            _router.On(MessageTypes.HoloSpawn, _ => { });

            _router.Route(Env(MessageTypes.HoloSpawn));
            _router.Route(Env("unknown"));

            Assert.AreEqual(2, anyCount);
        }

        [Test]
        public void MultipleHandlers_AllInvoked()
        {
            int a = 0, b = 0;
            _router.On(MessageTypes.HoloUpdate, _ => a++);
            _router.On(MessageTypes.HoloUpdate, _ => b++);

            _router.Route(Env(MessageTypes.HoloUpdate));

            Assert.AreEqual(1, a);
            Assert.AreEqual(1, b);
        }

        [Test]
        public void Off_RemovesHandler()
        {
            int count = 0;
            void Handler(Envelope _) => count++;
            _router.On(MessageTypes.HoloDestroy, Handler);
            _router.Off(MessageTypes.HoloDestroy, Handler);

            _router.Route(Env(MessageTypes.HoloDestroy));

            Assert.AreEqual(0, count);
        }

        [Test]
        public void Off_OneOfTwoHandlers_KeepsTheOther()
        {
            int a = 0, b = 0;
            void Ha(Envelope _) => a++;
            void Hb(Envelope _) => b++;
            _router.On(MessageTypes.HoloDestroy, Ha);
            _router.On(MessageTypes.HoloDestroy, Hb);
            _router.Off(MessageTypes.HoloDestroy, Ha);

            _router.Route(Env(MessageTypes.HoloDestroy));

            Assert.AreEqual(0, a);
            Assert.AreEqual(1, b);
        }

        [Test]
        public void Route_NullEnvelopeOrEmptyType_DoesNotThrow()
        {
            Assert.DoesNotThrow(() => _router.Route(null));
            Assert.DoesNotThrow(() => _router.Route(new Envelope { Type = null }));
            Assert.DoesNotThrow(() => _router.Route(new Envelope { Type = "" }));
        }

        [Test]
        public void On_NullArgs_AreIgnored()
        {
            Assert.DoesNotThrow(() => _router.On(null, _ => { }));
            Assert.DoesNotThrow(() => _router.On(MessageTypes.AgentSpeech, null));
        }

        [Test]
        public void Clear_RemovesAllHandlers()
        {
            int count = 0;
            _router.On(MessageTypes.AgentSpeech, _ => count++);
            _router.Clear();
            _router.Route(Env(MessageTypes.AgentSpeech));
            Assert.AreEqual(0, count);
        }
    }
}
