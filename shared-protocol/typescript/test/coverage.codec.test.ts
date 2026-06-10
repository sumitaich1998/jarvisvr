import { describe, expect, it } from "vitest";
import {
  PROTOCOL_VERSION,
  ProtocolValidationError,
  decode,
  encode,
  isValid,
  iterErrors,
  newId,
  newMessage,
  nowMs,
  validate,
} from "../src/index.js";
import { formatErrors } from "../src/codec.js";

describe("codec internals (branch coverage)", () => {
  it("newMessage honors id/ts/session/replyTo and payload defaults", () => {
    const m = newMessage("agent.speech", { text: "hi" }, "S", { id: "X", ts: 42, replyTo: "R" });
    expect(m).toMatchObject({ id: "X", ts: 42, session: "S", reply_to: "R", v: PROTOCOL_VERSION });
    const d = newMessage("client.heartbeat"); // no payload / session / opts
    expect(d.payload).toEqual({});
    expect(d.session).toBeUndefined();
    expect(d.reply_to).toBeUndefined();
    expect(typeof newId()).toBe("string");
    expect(nowMs()).toBeGreaterThan(0);
  });

  it("encode/decode round-trip strings and bytes", () => {
    const wire = encode(newMessage("client.ack", {}, "S"));
    expect(decode(wire).type).toBe("client.ack");
    const bytes = new TextEncoder().encode(wire);
    expect(decode(bytes).type).toBe("client.ack"); // Uint8Array branch
  });

  it("iterErrors accepts object, string, and bytes (toDoc branches)", () => {
    const good = { v: PROTOCOL_VERSION, id: "a", type: "client.ack", ts: 1, session: "S", payload: {} };
    expect(iterErrors(good)).toEqual([]);
    expect(iterErrors(JSON.stringify(good))).toEqual([]);
    expect(iterErrors(new TextEncoder().encode(JSON.stringify(good)))).toEqual([]);
  });

  it("iterErrors: unknown type tolerated by default, flagged when strict", () => {
    const m = { v: PROTOCOL_VERSION, id: "a", type: "vendor.x", ts: 1, payload: {} };
    expect(iterErrors(m)).toEqual([]);
    expect(iterErrors(m, { allowUnknownTypes: false })).toEqual([`unknown message type: "vendor.x"`]);
  });

  it("iterErrors: missing type skips payload validation but envelope still flags it", () => {
    const errs = iterErrors({ v: PROTOCOL_VERSION, id: "a", ts: 1, payload: {} });
    expect(errs.some((e) => e.includes("type"))).toBe(true);
  });

  it("iterErrors: known type with non-object payload (array and string)", () => {
    const arr = iterErrors({ v: PROTOCOL_VERSION, id: "a", type: "agent.speech", ts: 1, payload: [1, 2] });
    expect(arr.some((e) => e.includes("must be an object"))).toBe(true);
    const str = iterErrors({ v: PROTOCOL_VERSION, id: "a", type: "agent.speech", ts: 1, payload: "nope" });
    expect(str.some((e) => e.includes("must be an object"))).toBe(true);
  });

  it("iterErrors: a doc with no payload key exercises the `?? {}` branch", () => {
    // envelope requires payload, so it's flagged — but payload defaults to {} here.
    const errs = iterErrors({ v: PROTOCOL_VERSION, id: "a", type: "client.ack", ts: 1, session: "S" });
    expect(Array.isArray(errs)).toBe(true);
  });

  it("iterErrors: known type with invalid payload (envelope ok)", () => {
    const errs = iterErrors({ v: PROTOCOL_VERSION, id: "a", type: "agent.speech", ts: 1, session: "S", payload: {} });
    expect(errs.some((e) => e.includes("agent.speech payload"))).toBe(true);
  });

  it("validate throws; isValid returns boolean", () => {
    expect(() => validate({ v: "9.9.9", id: "a", type: "client.ack", ts: 1, payload: {} })).toThrow(
      ProtocolValidationError,
    );
    expect(isValid({ v: PROTOCOL_VERSION, id: "a", type: "client.ack", ts: 1, session: "S", payload: {} })).toBe(true);
    expect(isValid({ v: "9.9.9", id: "a", type: "client.ack", ts: 1, payload: {} })).toBe(false);
  });

  it("ProtocolValidationError uses fallback message for empty errors", () => {
    expect(new ProtocolValidationError([]).message).toBe("invalid message");
    const e = new ProtocolValidationError(["x", "y"]);
    expect(e.message).toBe("x; y");
    expect(e.errors).toEqual(["x", "y"]);
  });

  it("formatErrors covers null, root, nested, and missing-message branches", () => {
    expect(formatErrors("p", null)).toEqual([]);
    expect(formatErrors("p", undefined)).toEqual([]);
    expect(
      formatErrors("p", [
        { instancePath: "", message: "m1" } as never,
        { instancePath: "/x", message: undefined } as never,
      ]),
    ).toEqual(["p <root>: m1", "p /x: invalid"]);
  });
});
