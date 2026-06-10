using System;
using System.Collections.Generic;

namespace JarvisVR.Protocol
{
    /// <summary>
    /// Dispatches inbound envelopes to handlers keyed by message <c>type</c>.
    /// Conformance: unknown <c>type</c> values are ignored (forward-compatible, §6) and surfaced
    /// via <see cref="OnUnhandled"/> for optional logging.
    /// </summary>
    public class MessageRouter
    {
        private readonly Dictionary<string, Action<Envelope>> _handlers = new Dictionary<string, Action<Envelope>>();

        /// <summary>Fired for every routed envelope, before type-specific dispatch.</summary>
        public event Action<Envelope> OnAny;

        /// <summary>Fired when no handler is registered for a (valid) message type.</summary>
        public event Action<string, Envelope> OnUnhandled;

        public void On(string type, Action<Envelope> handler)
        {
            if (string.IsNullOrEmpty(type) || handler == null) return;
            _handlers[type] = _handlers.TryGetValue(type, out var existing) ? existing + handler : handler;
        }

        public void Off(string type, Action<Envelope> handler)
        {
            if (string.IsNullOrEmpty(type) || handler == null) return;
            if (!_handlers.TryGetValue(type, out var existing)) return;
            var combined = existing - handler;
            if (combined == null) _handlers.Remove(type);
            else _handlers[type] = combined;
        }

        public void Clear() => _handlers.Clear();

        public void Route(Envelope env)
        {
            if (env == null || string.IsNullOrEmpty(env.Type)) return;
            OnAny?.Invoke(env);
            if (_handlers.TryGetValue(env.Type, out var handler))
                handler.Invoke(env);
            else
                OnUnhandled?.Invoke(env.Type, env); // unknown type -> ignored per protocol
        }
    }
}
