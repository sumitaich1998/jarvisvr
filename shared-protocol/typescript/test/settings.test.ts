import { describe, expect, it } from "vitest";
import {
  type ClientSettingsGet,
  type ClientSettingsUpdate,
  MessageType,
  type ServerSettings,
  decode,
  encode,
  isValid,
  iterErrors,
  newMessage,
  validate,
} from "../src/index.js";

const SERVER_SETTINGS: ServerSettings = {
  llm: {
    current: { provider: "openai", model: "gpt-4o", base_url: null, key_set: true },
    providers: [
      {
        id: "openai",
        name: "OpenAI",
        default_model: "gpt-4o",
        models: ["gpt-4o", "gpt-4o-mini"],
        needs_key: true,
        needs_base_url: false,
        key_set: true,
        capabilities: { tools: true, vision: true },
      },
      {
        id: "ollama",
        name: "Ollama (local)",
        default_model: "llama3.1",
        needs_key: false,
        needs_base_url: true,
        key_set: false,
        capabilities: { tools: true, vision: false },
      },
    ],
  },
};

const cases: Array<[string, Record<string, unknown>]> = [
  [MessageType.CLIENT_SETTINGS_GET, { section: "llm" } satisfies ClientSettingsGet],
  [
    MessageType.CLIENT_SETTINGS_UPDATE,
    { llm: { provider: "openai", model: "gpt-4o", base_url: null, api_key: "sk-secret" } } satisfies ClientSettingsUpdate,
  ],
  [MessageType.SERVER_SETTINGS, SERVER_SETTINGS as unknown as Record<string, unknown>],
];

describe("v1.1 §5.15 settings round-trip", () => {
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

  it("server.settings NEVER contains an api_key (closed schema)", () => {
    const leak = {
      llm: {
        current: { provider: "openai", model: "gpt-4o", key_set: true, api_key: "sk-x" },
        providers: [],
      },
    };
    expect(isValid({ v: "1.1.0", id: "x", type: "server.settings", ts: 1, payload: leak })).toBe(false);
    expect(() => validate({ v: "1.1.0", id: "x", type: "server.settings", ts: 1, payload: leak })).toThrow();

    const leakInProvider = {
      llm: {
        current: { provider: "openai", model: "gpt-4o", key_set: true },
        providers: [
          {
            id: "openai",
            name: "OpenAI",
            default_model: "gpt-4o",
            needs_key: true,
            needs_base_url: false,
            key_set: true,
            capabilities: { tools: true, vision: true },
            api_key: "sk-x",
          },
        ],
      },
    };
    expect(isValid({ v: "1.1.0", id: "x", type: "server.settings", ts: 1, payload: leakInProvider })).toBe(false);
  });

  it("rejects malformed settings", () => {
    expect(isValid({ v: "1.1.0", id: "x", type: "server.settings", ts: 1, payload: {} })).toBe(false);
    expect(isValid({ v: "1.1.0", id: "x", type: "client.settings_get", ts: 1, payload: { section: "everything" } })).toBe(false);
  });
});
