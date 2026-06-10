using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Protocol
{
    /// <summary>
    /// The v1 wire envelope (PROTOCOL.md §2). The <see cref="Payload"/> is kept as a
    /// raw <see cref="JObject"/>; use <see cref="PayloadAs{T}"/> to materialize a DTO.
    /// </summary>
    public class Envelope
    {
        [JsonProperty("v")]
        public string V { get; set; } = Protocol.Version;

        [JsonProperty("id")]
        public string Id { get; set; }

        [JsonProperty("type")]
        public string Type { get; set; }

        [JsonProperty("ts")]
        public long Ts { get; set; }

        [JsonProperty("session", NullValueHandling = NullValueHandling.Ignore)]
        public string Session { get; set; }

        [JsonProperty("reply_to", NullValueHandling = NullValueHandling.Ignore)]
        public string ReplyTo { get; set; }

        [JsonProperty("payload")]
        public JObject Payload { get; set; } = new JObject();

        /// <summary>Deserialize the payload into a typed DTO (e.g. <c>PayloadAs&lt;HoloObject&gt;()</c>).</summary>
        public T PayloadAs<T>()
        {
            return Payload == null ? default : Payload.ToObject<T>(JarvisProtocol.Serializer);
        }

        /// <summary>Replace the payload from a typed DTO (null fields are omitted).</summary>
        public void SetPayload(object payload)
        {
            Payload = payload == null ? new JObject() : JObject.FromObject(payload, JarvisProtocol.Serializer);
        }
    }
}
