import { describe, expect, it } from "vitest";
import {
  MessageType,
  PROTOCOL_VERSION,
  SUPPORTED_VERSIONS,
  type ServerAuthoring,
  type ServerTrace,
  type TraceEvent,
  decode,
  encode,
  isValid,
  iterErrors,
  newMessage,
} from "../src/index.js";

const cases: Array<[string, Record<string, unknown>]> = [
  [MessageType.CLIENT_TRACE_SUBSCRIBE, { enabled: true }],
  [MessageType.CLIENT_TRACE_GET, { plan_id: "P1" }],
  [MessageType.CLIENT_AGENT_INSPECT, { role: "research-agent" }],
  [MessageType.CLIENT_AUTHOR_LIST, {}],
  [MessageType.CLIENT_AUTHOR_SKILL, {
    op: "create", name: "track-habit", category: "productivity", agent: "productivity-agent",
    description: "Track a habit.", body: "# Track", allowed_tools: ["take_note"],
  }],
  [MessageType.CLIENT_AUTHOR_AGENT, {
    op: "create", role: "finance-agent", name: "Finance", persona: "Meticulous.", tools: ["get_stocks"],
  }],
  [MessageType.ORCHESTRATION_TRACE_EVENT, {
    plan_id: "P1", seq: 3, ts: 1733397600000, agent_id: "a1", role: "research-agent",
    parent: "jarvis", level: 1, kind: "tool_call", label: "get_weather(city=Tokyo)",
    tool: "get_weather", detail: "ok", duration_ms: 12,
  } satisfies TraceEvent as unknown as Record<string, unknown>],
  [MessageType.SERVER_TRACE, {
    plan_id: "P1", goal: "g",
    agents: [{ agent_id: "a1", role: "research-agent", parent: "jarvis", level: 1 }],
    entries: [{ plan_id: "P1", seq: 0, ts: 1, agent_id: "a1", role: "research-agent", kind: "memory_read", label: "recalled 0" }],
  } satisfies ServerTrace as unknown as Record<string, unknown>],
  [MessageType.SERVER_AGENT_INFO, {
    role: "research-agent", name: "Research", source: "builtin", persona: "p",
    tools: ["get_weather"], skills: [{ name: "web-research", description: "d", source: "builtin" }],
    memory: { summary: "1 item", items: 1, recent: [{ ts: 1, text: "t" }] },
  }],
  [MessageType.SERVER_AUTHORING, {
    agents: [{ role: "research-agent", name: "Research", source: "builtin", skills: ["web-research"], tools: ["get_weather"] }],
    skills: [{ name: "web-research", agent: "research-agent", category: "research", source: "builtin", description: "d" }],
    categories: ["research"], tools: ["get_weather"],
  } satisfies ServerAuthoring as unknown as Record<string, unknown>],
];

describe("v1.3 §10 tracing + authoring round-trip", () => {
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

  it("rejects malformed v1.3 messages", () => {
    expect(isValid({ v: "1.3.0", id: "x", type: "orchestration.trace_event", ts: 1, payload: { plan_id: "P", seq: 0, ts: 1, agent_id: "a", role: "r", label: "x" } })).toBe(false);
    expect(isValid({ v: "1.3.0", id: "x", type: "orchestration.trace_event", ts: 1, payload: { plan_id: "P", seq: 0, ts: 1, agent_id: "a", role: "r", kind: "napping", label: "x" } })).toBe(false);
    expect(isValid({ v: "1.3.0", id: "x", type: "client.author_skill", ts: 1, payload: { op: "create" } })).toBe(false);
    expect(isValid({ v: "1.3.0", id: "x", type: "client.author_agent", ts: 1, payload: { op: "create" } })).toBe(false);
    expect(isValid({ v: "1.3.0", id: "x", type: "client.agent_inspect", ts: 1, payload: {} })).toBe(false);
    expect(isValid({ v: "1.3.0", id: "x", type: "server.authoring", ts: 1, payload: { agents: [] } })).toBe(false);
    expect(isValid({ v: "1.3.0", id: "x", type: "client.trace_subscribe", ts: 1, payload: {} })).toBe(false);
  });

  it("bumped version + backward compatibility", () => {
    expect(PROTOCOL_VERSION).toBe("1.3.0");
    for (const v of ["1.0.0", "1.1.0", "1.2.0", "1.3.0"]) {
      expect(SUPPORTED_VERSIONS).toContain(v);
    }
    expect(isValid(`{"v":"1.2.0","id":"a","type":"agent.speech","ts":1,"session":"S","payload":{"text":"hi","final":true}}`, { allowUnknownTypes: false })).toBe(true);
  });
});
