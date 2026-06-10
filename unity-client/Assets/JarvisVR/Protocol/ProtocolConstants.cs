// JarvisVR wire protocol v1 — see /docs/PROTOCOL.md (the source of truth).
//
// NOTE: shared-protocol/ will also publish canonical C# bindings for these messages.
// This implementation is intentionally self-contained so the Unity client is not blocked
// on that package. When shared-protocol lands, these types can be reconciled / replaced
// (keep the wire shapes identical; only the C# packaging should change).

namespace JarvisVR.Protocol
{
    /// <summary>Protocol-wide constants from docs/PROTOCOL.md.</summary>
    public static class ProtocolConstants
    {
        /// <summary>Semantic version carried in the envelope <c>v</c> field. v1.3 adds §10 tracing +
        /// authoring; v1.2 added §9 orchestration; v1.1 added §8 perception. Inbound versions are
        /// never rejected (unknown types are ignored).</summary>
        public const string Version = "1.3.0";

        /// <summary>Default WebSocket path for the main JSON channel.</summary>
        public const string DefaultPath = "/jarvis";

        /// <summary>Optional parallel binary audio channel (16 kHz mono PCM16).</summary>
        public const string AudioPath = "/audio";

        /// <summary>Optional parallel binary vision channel (length-prefixed JPEG frames, §8.2).</summary>
        public const string VisionPath = "/vision";

        /// <summary>Default server port.</summary>
        public const int DefaultPort = 8765;

        /// <summary>Heartbeat cadence (client → server) in seconds.</summary>
        public const float HeartbeatSeconds = 5f;
    }
}
