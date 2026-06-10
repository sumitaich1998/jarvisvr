using System.Collections.Generic;
using Newtonsoft.Json;

namespace JarvisVR.Protocol
{
    // ---------------------------------------------------------------------------------------------
    // v1.2 Multi-Agent Orchestration payloads (docs/PROTOCOL.md §9 / ORCHESTRATION.md).
    // Additive + optional: a client may ignore these and behave exactly as v1.1. Self-contained;
    // shared-protocol will publish canonical C# bindings to reconcile with later.
    // ---------------------------------------------------------------------------------------------

    /// <summary>§9.2 orchestration.plan — the agent team Jarvis built for a goal (nodes + edges).</summary>
    public class OrchestrationPlan
    {
        [JsonProperty("plan_id")] public string PlanId;
        [JsonProperty("goal", NullValueHandling = NullValueHandling.Ignore)] public string Goal;
        [JsonProperty("agents")] public List<PlanAgent> Agents = new List<PlanAgent>();
        [JsonProperty("edges", NullValueHandling = NullValueHandling.Ignore)] public List<PlanEdge> Edges = new List<PlanEdge>();
    }

    public class PlanAgent
    {
        [JsonProperty("agent_id")] public string AgentId;
        [JsonProperty("role")] public string Role;
        [JsonProperty("name", NullValueHandling = NullValueHandling.Ignore)] public string Name;
        [JsonProperty("parent")] public string Parent;          // null for the orchestrator root
        [JsonProperty("level")] public int Level;
        [JsonProperty("subtask", NullValueHandling = NullValueHandling.Ignore)] public string Subtask;
        [JsonProperty("skills", NullValueHandling = NullValueHandling.Ignore)] public List<string> Skills;
    }

    public class PlanEdge
    {
        [JsonProperty("from")] public string From;
        [JsonProperty("to")] public string To;
    }

    /// <summary>§9.2 orchestration.agent_status — one agent's lifecycle/progress update.</summary>
    public class AgentStatus
    {
        [JsonProperty("plan_id", NullValueHandling = NullValueHandling.Ignore)] public string PlanId;
        [JsonProperty("agent_id")] public string AgentId;
        [JsonProperty("role", NullValueHandling = NullValueHandling.Ignore)] public string Role;
        [JsonProperty("parent", NullValueHandling = NullValueHandling.Ignore)] public string Parent;
        [JsonProperty("level", NullValueHandling = NullValueHandling.Ignore)] public int Level;
        // queued | planning | working | delegating | waiting | done | failed
        [JsonProperty("state")] public string State;
        [JsonProperty("skill", NullValueHandling = NullValueHandling.Ignore)] public string Skill;
        [JsonProperty("label", NullValueHandling = NullValueHandling.Ignore)] public string Label;
        [JsonProperty("progress", NullValueHandling = NullValueHandling.Ignore)] public float? Progress;
    }

    /// <summary>§9.2 orchestration.handoff — a delegation to another agent / sub-agent.</summary>
    public class AgentHandoff
    {
        [JsonProperty("plan_id", NullValueHandling = NullValueHandling.Ignore)] public string PlanId;
        [JsonProperty("from_agent")] public string FromAgent;
        [JsonProperty("to_agent")] public string ToAgent;
        [JsonProperty("to_role", NullValueHandling = NullValueHandling.Ignore)] public string ToRole;
        [JsonProperty("level", NullValueHandling = NullValueHandling.Ignore)] public int Level;
        [JsonProperty("subtask", NullValueHandling = NullValueHandling.Ignore)] public string Subtask;
        [JsonProperty("reason", NullValueHandling = NullValueHandling.Ignore)] public string Reason;
    }
}
