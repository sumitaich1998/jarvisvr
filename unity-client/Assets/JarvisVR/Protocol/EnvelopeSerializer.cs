using System;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Protocol
{
    /// <summary>
    /// (De)serializes the v1 envelope to/from JSON text frames and builds outbound messages.
    /// Configured to be forward-compatible: unknown payload members are ignored, and null
    /// fields (e.g. an omitted <c>session</c>) are not written.
    /// </summary>
    public static class EnvelopeSerializer
    {
        public static readonly JsonSerializerSettings Settings = new JsonSerializerSettings
        {
            NullValueHandling = NullValueHandling.Ignore,
            MissingMemberHandling = MissingMemberHandling.Ignore,
            DateParseHandling = DateParseHandling.None,
            Formatting = Formatting.None,
        };

        /// <summary>Shared serializer used for payload (de)serialization.</summary>
        public static readonly JsonSerializer Json = JsonSerializer.Create(Settings);

        public static string Serialize(Envelope env) => JsonConvert.SerializeObject(env, Settings);

        public static Envelope Deserialize(string json) => JsonConvert.DeserializeObject<Envelope>(json, Settings);

        /// <summary>Parse safely; returns false (without throwing) on malformed input.</summary>
        public static bool TryDeserialize(string json, out Envelope env, out string error)
        {
            try
            {
                env = Deserialize(json);
                if (env == null || string.IsNullOrEmpty(env.Type))
                {
                    error = "missing type";
                    return false;
                }
                error = null;
                return true;
            }
            catch (Exception e)
            {
                env = null;
                error = e.Message;
                return false;
            }
        }

        /// <summary>Build an envelope around a payload object (auto id + timestamp).</summary>
        public static Envelope Build(string type, object payload, string session, string id = null, string replyTo = null)
        {
            return new Envelope
            {
                V = ProtocolConstants.Version,
                Id = string.IsNullOrEmpty(id) ? Guid.NewGuid().ToString() : id,
                Type = type,
                Ts = NowMs(),
                Session = session,
                ReplyTo = replyTo,
                Payload = payload == null ? new JObject() : JObject.FromObject(payload, Json),
            };
        }

        /// <summary>Convenience: build + serialize in one step.</summary>
        public static string BuildJson(string type, object payload, string session, string id = null, string replyTo = null)
            => Serialize(Build(type, payload, session, id, replyTo));

        public static long NowMs() => DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
    }
}
