import { describe, expect, it } from "vitest";
import { SCHEMA_DIR, ajv, envelopeValidator, loadSchemas, payloadValidator } from "../src/index.js";
import { findSchemaDir } from "../src/schemas.js";

describe("schemas internals (branch coverage)", () => {
  it("findSchemaDir: env override branch", () => {
    expect(findSchemaDir({ env: SCHEMA_DIR })).toBe(SCHEMA_DIR);
  });

  it("findSchemaDir: default upward search", () => {
    expect(findSchemaDir()).toBe(SCHEMA_DIR);
  });

  it("findSchemaDir: throws when nothing is found", () => {
    expect(() => findSchemaDir({ env: "", startDir: "/no/such/jarvis/schema/dir" })).toThrow(/Could not locate/);
  });

  it("loadSchemas is cached and contains the envelope schema", () => {
    const a = loadSchemas();
    const b = loadSchemas();
    expect(a).toBe(b); // memoized
    expect("envelope.schema.json" in a).toBe(true);
  });

  it("ajv() is cached", () => {
    expect(ajv()).toBe(ajv());
  });

  it("envelopeValidator returns a compiled validator", () => {
    expect(typeof envelopeValidator()).toBe("function");
  });

  it("payloadValidator: known -> fn, unknown -> null", () => {
    expect(typeof payloadValidator("agent.speech")).toBe("function");
    expect(payloadValidator("totally.unknown")).toBeNull();
  });
});
