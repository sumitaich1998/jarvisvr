import { describe, expect, it } from "vitest";
import {
  type AgentSpeech,
  type ClientBargeIn,
  type ClientHello,
  type HoloObject,
  MessageType,
  PROTOCOL_VERSION,
  type ServerHelloAck,
  type TextInput,
  decode,
  encode,
  isValid,
  iterErrors,
  newMessage,
  nowMs,
  validate,
} from "../src/index.js";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const cases: Array<[string, Record<string, unknown>]> = [
  [
    MessageType.CLIENT_HELLO,
    {
      device: "quest3",
      app_version: "0.1.0",
      protocol_version: PROTOCOL_VERSION,
      capabilities: { passthrough: true, hand_tracking: true, mic: true },
      locale: "en-US",
    } satisfies ClientHello,
  ],
  [
    MessageType.SERVER_HELLO_ACK,
    {
      session: "S1",
      protocol_version: PROTOCOL_VERSION,
      agent: { name: "Jarvis", model: "mock" },
      tools: ["get_weather", "start_timer"],
      voice: { tts: true, wake_word: "jarvis" },
    } satisfies ServerHelloAck,
  ],
  [MessageType.USER_VOICE_TRANSCRIPT, { text: "weather in tokyo", confidence: 0.97 } satisfies TextInput],
  [MessageType.AGENT_SPEECH, { text: "Here's Tokyo.", final: true } satisfies AgentSpeech],
  [
    MessageType.HOLO_SPAWN,
    {
      object_id: "O1",
      widget_type: "weather_orb",
      transform: { anchor: "head", position: [0.3, 0, 0.8], rotation: [0, 0, 0, 1], scale: [1, 1, 1], billboard: true },
      props: { city: "Tokyo", temp_c: 18 },
      interactable: true,
      interactions: ["grab", "tap"],
    } satisfies HoloObject,
  ],
  [MessageType.CLIENT_HEARTBEAT, {}],
  [MessageType.CLIENT_BARGE_IN, { reason: "user_speech" } satisfies ClientBargeIn],
];

describe("round-trip", () => {
  for (const [type, payload] of cases) {
    it(`${type} encodes, decodes, and validates`, () => {
      const msg = newMessage(type, payload, "S");
      const wire = encode(msg);
      expect(typeof wire).toBe("string");
      const decoded = decode(wire);
      expect(decoded.type).toBe(type);
      expect(decoded.payload).toEqual(payload);
      // strict-type validation (all known types)
      expect(iterErrors(msg, { allowUnknownTypes: false })).toEqual([]);
      expect(isValid(msg)).toBe(true);
      validate(wire);
    });
  }

  it("new_message has a uuid id and epoch-ms ts", () => {
    const before = nowMs();
    const msg = newMessage(MessageType.AGENT_SPEECH, { text: "hi" });
    const after = nowMs();
    expect(msg.id).toMatch(UUID_RE);
    expect(msg.ts).toBeGreaterThanOrEqual(before);
    expect(msg.ts).toBeLessThanOrEqual(after);
    expect(msg.v).toBe(PROTOCOL_VERSION);
  });

  it("client.barge_in accepts an empty payload (idempotent no-op)", () => {
    const empty = newMessage(MessageType.CLIENT_BARGE_IN, {}, "S");
    expect(isValid(empty, { allowUnknownTypes: false })).toBe(true);
    const withReason = newMessage<ClientBargeIn>(MessageType.CLIENT_BARGE_IN, { reason: "user_speech" }, "S");
    expect(iterErrors(withReason, { allowUnknownTypes: false })).toEqual([]);
  });

  it("first hello omits session and reply_to", () => {
    const msg = newMessage(MessageType.CLIENT_HELLO, { device: "quest3", protocol_version: PROTOCOL_VERSION });
    const wire = encode(msg);
    expect(wire).not.toContain("session");
    expect(wire).not.toContain("reply_to");
    expect(isValid(wire)).toBe(true);
  });

  it("rejects malformed messages", () => {
    expect(isValid({ v: "1.0.0", id: "x", type: "agent.speech", ts: 1, payload: { final: true } })).toBe(false);
    expect(isValid({ v: "2.0.0", id: "x", type: "agent.speech", ts: 1, payload: { text: "hi" } })).toBe(false);
    expect(
      isValid({
        v: "1.0.0",
        id: "x",
        type: "holo.spawn",
        ts: 1,
        payload: { object_id: "O1", widget_type: "w", transform: { anchor: "head", position: [0, 0], rotation: [0, 0, 0, 1], scale: [1, 1, 1] } },
      }),
    ).toBe(false);
  });
});
