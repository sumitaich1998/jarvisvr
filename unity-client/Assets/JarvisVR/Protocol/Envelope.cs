using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Protocol
{
    /// <summary>
    /// The universal message envelope (docs/PROTOCOL.md §2). Every frame on the wire is a JSON
    /// object with exactly these fields. The <c>payload</c> is kept as a raw <see cref="JObject"/>
    /// so the router can dispatch by <c>type</c> first and deserialize the strongly-typed payload
    /// only when a handler needs it (and so unknown payload keys are ignored = forward-compatible).
    /// </summary>
    public class Envelope
    {
        [JsonProperty("v")]
        public string V = ProtocolConstants.Version;

        [JsonProperty("id")]
        public string Id;

        [JsonProperty("type")]
        public string Type;

        [JsonProperty("ts")]
        public long Ts;

        // Omitted on the very first client.hello; assigned by the server in hello_ack.
        [JsonProperty("session", NullValueHandling = NullValueHandling.Ignore)]
        public string Session;

        // Optional correlation id (e.g. client.ack -> the spawn command's id).
        [JsonProperty("reply_to", NullValueHandling = NullValueHandling.Ignore)]
        public string ReplyTo;

        [JsonProperty("payload")]
        public JObject Payload = new JObject();

        /// <summary>Deserialize the payload into a strongly-typed DTO (ignores unknown keys).</summary>
        public T PayloadAs<T>() where T : class
        {
            if (Payload == null) return null;
            return Payload.ToObject<T>(EnvelopeSerializer.Json);
        }
    }
}
