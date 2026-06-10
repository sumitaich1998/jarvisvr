using System.Collections.Generic;
using Newtonsoft.Json;

namespace JarvisVR.Protocol
{
    // ---------------------------------------------------------------------------------------------
    // v1.3 Per-agent tracing payloads (docs/PROTOCOL.md §10.1). Additive + optional.
    // Traces are secret-redacted server-side; the client never logs `detail`.
    // Self-contained; shared-protocol will publish canonical C# bindings.
    // ---------------------------------------------------------------------------------------------

    /// <summary>§10.1 client.trace_subscribe — turn live trace_event streaming on/off.</summary>
    public class TraceSubscribe
    {
        [JsonProperty("enabled")] public bool Enabled;

        public TraceSubscribe() { }
        public TraceSubscribe(bool enabled) { Enabled = enabled; }
    }

    /// <summary>§10.1 orchestration.trace_event — one live per-agent trace entry.</summary>
    public class AgentTraceEvent
    {
        [JsonProperty("plan_id", NullValueHandling = NullValueHandling.Ignore)] public string PlanId;
        [JsonProperty("seq", NullValueHandling = NullValueHandling.Ignore)] public long Seq;
        [JsonProperty("ts", NullValueHandling = NullValueHandling.Ignore)] public long Ts;
        [JsonProperty("agent_id")] public string AgentId;
        [JsonProperty("role", NullValueHandling = NullValueHandling.Ignore)] public string Role;
        [JsonProperty("parent", NullValueHandling = NullValueHandling.Ignore)] public string Parent;
        [JsonProperty("level", NullValueHandling = NullValueHandling.Ignore)] public int Level;
        // memory_read | memory_write | skill_activated | tool_call | tool_result | observation | delegated | speech | error
        [JsonProperty("kind")] public string Kind;
        [JsonProperty("label", NullValueHandling = NullValueHandling.Ignore)] public string Label;
        [JsonProperty("skill", NullValueHandling = NullValueHandling.Ignore)] public string Skill;
        [JsonProperty("tool", NullValueHandling = NullValueHandling.Ignore)] public string Tool;
        [JsonProperty("detail", NullValueHandling = NullValueHandling.Ignore)] public string Detail;
        [JsonProperty("duration_ms", NullValueHandling = NullValueHandling.Ignore)] public int? DurationMs;
    }

    /// <summary>§10.1 client.trace_get — fetch a past turn's full trace (omit plan_id for latest).</summary>
    public class TraceGet
    {
        [JsonProperty("plan_id", NullValueHandling = NullValueHandling.Ignore)] public string PlanId;

        public TraceGet() { }
        public TraceGet(string planId) { PlanId = planId; }
    }

    /// <summary>§10.1 server.trace — full trace for a turn.</summary>
    public class ServerTrace
    {
        [JsonProperty("plan_id", NullValueHandling = NullValueHandling.Ignore)] public string PlanId;
        [JsonProperty("goal", NullValueHandling = NullValueHandling.Ignore)] public string Goal;
        [JsonProperty("agents", NullValueHandling = NullValueHandling.Ignore)] public List<TraceAgent> Agents;
        [JsonProperty("entries", NullValueHandling = NullValueHandling.Ignore)] public List<AgentTraceEvent> Entries;
    }

    public class TraceAgent
    {
        [JsonProperty("agent_id")] public string AgentId;
        [JsonProperty("role", NullValueHandling = NullValueHandling.Ignore)] public string Role;
        [JsonProperty("parent", NullValueHandling = NullValueHandling.Ignore)] public string Parent;
        [JsonProperty("level", NullValueHandling = NullValueHandling.Ignore)] public int Level;
    }

    /// <summary>§10.1 client.agent_inspect — inspect an agent (by role or agent_id).</summary>
    public class AgentInspect
    {
        [JsonProperty("role", NullValueHandling = NullValueHandling.Ignore)] public string Role;
        [JsonProperty("agent_id", NullValueHandling = NullValueHandling.Ignore)] public string AgentId;
    }

    /// <summary>§10.1 server.agent_info — an agent's persona/skills/tools/memory.</summary>
    public class ServerAgentInfo
    {
        [JsonProperty("role", NullValueHandling = NullValueHandling.Ignore)] public string Role;
        [JsonProperty("name", NullValueHandling = NullValueHandling.Ignore)] public string Name;
        [JsonProperty("source", NullValueHandling = NullValueHandling.Ignore)] public string Source; // builtin | user
        [JsonProperty("persona", NullValueHandling = NullValueHandling.Ignore)] public string Persona;
        [JsonProperty("tools", NullValueHandling = NullValueHandling.Ignore)] public List<string> Tools;
        [JsonProperty("skills", NullValueHandling = NullValueHandling.Ignore)] public List<AgentInfoSkill> Skills;
        [JsonProperty("memory", NullValueHandling = NullValueHandling.Ignore)] public AgentMemory Memory;
    }

    public class AgentInfoSkill
    {
        [JsonProperty("name")] public string Name;
        [JsonProperty("description", NullValueHandling = NullValueHandling.Ignore)] public string Description;
        [JsonProperty("source", NullValueHandling = NullValueHandling.Ignore)] public string Source;
    }

    public class AgentMemory
    {
        [JsonProperty("summary", NullValueHandling = NullValueHandling.Ignore)] public string Summary;
        [JsonProperty("items", NullValueHandling = NullValueHandling.Ignore)] public int Items;
        [JsonProperty("recent", NullValueHandling = NullValueHandling.Ignore)] public List<MemoryItem> Recent;
    }

    public class MemoryItem
    {
        [JsonProperty("ts", NullValueHandling = NullValueHandling.Ignore)] public long Ts;
        [JsonProperty("text", NullValueHandling = NullValueHandling.Ignore)] public string Text;
    }
}
