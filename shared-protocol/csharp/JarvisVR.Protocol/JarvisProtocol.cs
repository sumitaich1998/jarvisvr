using System;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Protocol
{
    /// <summary>
    /// Static (de)serializer for JarvisVR messages, mirroring the Python
    /// <c>jarvis_protocol</c> binding. Newtonsoft-based so Unity can drop it in.
    /// </summary>
    public static class JarvisProtocol
    {
        /// <summary>Canonical serializer settings: omit nulls, ignore unknown members.</summary>
        public static readonly JsonSerializerSettings Settings = new JsonSerializerSettings
        {
            NullValueHandling = NullValueHandling.Ignore,
            MissingMemberHandling = MissingMemberHandling.Ignore,
            Formatting = Formatting.None,
        };

        /// <summary>Shared <see cref="JsonSerializer"/> built from <see cref="Settings"/>.</summary>
        public static readonly JsonSerializer Serializer = JsonSerializer.Create(Settings);

        /// <summary>Serialize an envelope to a compact JSON text frame.</summary>
        public static string Encode(Envelope message)
        {
            return JsonConvert.SerializeObject(message, Settings);
        }

        /// <summary>Parse a JSON text frame into an <see cref="Envelope"/>.</summary>
        public static Envelope Decode(string json)
        {
            return JsonConvert.DeserializeObject<Envelope>(json, Settings);
        }

        /// <summary>
        /// Build an envelope with a fresh UUID <c>id</c> and epoch-ms <c>ts</c>.
        /// <paramref name="payload"/> may be any DTO or a <see cref="JObject"/>.
        /// </summary>
        public static Envelope NewMessage(string type, object payload = null, string session = null, string replyTo = null)
        {
            JObject body;
            if (payload == null)
            {
                body = new JObject();
            }
            else if (payload is JObject obj)
            {
                body = obj;
            }
            else
            {
                body = JObject.FromObject(payload, Serializer);
            }

            return new Envelope
            {
                V = Protocol.Version,
                Id = Guid.NewGuid().ToString(),
                Type = type,
                Ts = NowMs(),
                Session = session,
                ReplyTo = replyTo,
                Payload = body,
            };
        }

        /// <summary>Current time as epoch milliseconds (sender clock).</summary>
        public static long NowMs()
        {
            return DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
        }

        /// <summary>Convenience wrapper for <see cref="Envelope.PayloadAs{T}"/>.</summary>
        public static T PayloadAs<T>(Envelope message)
        {
            return message == null ? default : message.PayloadAs<T>();
        }
    }
}
