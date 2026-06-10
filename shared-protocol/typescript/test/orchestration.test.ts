import { describe, expect, it } from "vitest";
import {
  MessageType,
  type OrchestrationAgentStatus,
  type OrchestrationHandoff,
  type OrchestrationPlan,
  PROTOCOL_VERSION,
  SUPPORTED_VERSIONS,
  decode,
  encode,
  isValid,
  iterErrors,
  newMessage,
  validate,
} from "../src/index.js";

const PLAN: OrchestrationPlan = {
  plan_id: "P1",
  goal: "show the weather in Tokyo and start a 5-minute timer",
  agents: [
    { agent_id: "jarvis", role: "orchestrator", name: "Jarvis", parent: null, level: 0 },
    { agent_id: "a1", role: "research-agent", name: "Research", parent: "jarvis", level: 1, subtask: "Tokyo weather", skills: ["web-research"] },
    { agent_id: "a2", role: "productivity-agent", name: "Productivity", parent: "jarvis", level: 1, subtask: "5-min timer", skills: ["manage-timers"] },
  ],
  edges: [
    { from: "jarvis", to: "a1" },
    { from: "jarvis", to: "a2" },
  ],
};

const cases: Array<[string, Record<string, unknown>]> = [
  [MessageType.ORCHESTRATION_PLAN, PLAN as unknown as Record<string, unknown>],
  [
    MessageType.ORCHESTRATION_AGENT_STATUS,
    { plan_id: "P1", agent_id: "a1", role: "research-agent", parent: "jarvis", level: 1, state: "working", skill: "web-research", label: "Looking up…", progress: 0.5 } satisfies OrchestrationAgentStatus,
  ],
  [
    MessageType.ORCHESTRATION_HANDOFF,
    { plan_id: "P1", from_agent: "a1", to_agent: "a1.1", to_role: "summarizer", level: 2, subtask: "summarize sources", reason: "delegating" } satisfies OrchestrationHandoff,
  ],
];

describe("v1.2 §9 orchestration round-trip", () => {
  for (const [type, payload] of cases) {
    it(`${type} encodes, decodes, and validates`, () => {
      const msg = newMessage(type, payload, "S");
      expect(msg.v).toBe("1.3.0");
      const decoded = decode(encode(msg));
      expect(decoded.type).toBe(type);
      expect(decoded.payload).toEqual(payload);
      expect(iterErrors(msg, { allowUnknownTypes: false })).toEqual([]);
      expect(isValid(msg)).toBe(true);
    });
  }

  it("agent.thinking may carry agent_id/role/skill", () => {
    const msg = newMessage(MessageType.AGENT_THINKING, {
      stage: "looking", tool: "identify_object", agent_id: "a3", role: "perception-agent", skill: "identify-object",
    });
    expect(isValid(msg, { allowUnknownTypes: false })).toBe(true);
    validate(msg);
  });

  it("rejects malformed orchestration messages", () => {
    expect(isValid({ v: "1.2.0", id: "x", type: "orchestration.plan", ts: 1, payload: { goal: "g", agents: [] } })).toBe(false);
    expect(isValid({ v: "1.2.0", id: "x", type: "orchestration.agent_status", ts: 1, payload: { plan_id: "P", agent_id: "a1", role: "r" } })).toBe(false);
    expect(isValid({ v: "1.2.0", id: "x", type: "orchestration.agent_status", ts: 1, payload: { plan_id: "P", agent_id: "a1", role: "r", state: "napping" } })).toBe(false);
    expect(isValid({ v: "1.2.0", id: "x", type: "orchestration.handoff", ts: 1, payload: { plan_id: "P", from_agent: "a1", to_agent: "a1.1" } })).toBe(false);
  });

  it("bumped version + backward compatibility", () => {
    expect(PROTOCOL_VERSION).toBe("1.3.0");
    expect(SUPPORTED_VERSIONS).toContain("1.0.0");
    expect(SUPPORTED_VERSIONS).toContain("1.1.0");
    expect(SUPPORTED_VERSIONS).toContain("1.2.0");
    expect(isValid(`{"v":"1.1.0","id":"a","type":"agent.speech","ts":1,"session":"S","payload":{"text":"hi","final":true}}`, { allowUnknownTypes: false })).toBe(true);
  });
});
