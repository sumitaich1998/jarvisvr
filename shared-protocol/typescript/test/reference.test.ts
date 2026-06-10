import { describe, expect, it } from "vitest";
import { type HoloObject, decode, isValid, validate } from "../src/index.js";

// Verbatim from docs/PROTOCOL.md §7. Short non-UUID ids must validate.
const REFERENCE: string[] = [
  `{"v":"1.0.0","id":"a1","type":"user.voice_transcript","ts":1,"session":"S","payload":{"text":"weather in tokyo"}}`,
  `{"v":"1.0.0","id":"b1","type":"agent.thinking","ts":2,"session":"S","payload":{"stage":"tool_call","tool":"get_weather"}}`,
  `{"v":"1.0.0","id":"b2","type":"agent.speech","ts":3,"session":"S","payload":{"text":"Here's Tokyo.","final":true}}`,
  `{"v":"1.0.0","id":"b3","type":"holo.spawn","ts":4,"session":"S","payload":{"object_id":"O1","widget_type":"weather_orb","transform":{"anchor":"head","position":[0.3,0,0.8],"rotation":[0,0,0,1],"scale":[1,1,1],"billboard":true},"props":{"city":"Tokyo","temp_c":18,"condition":"clouds"},"interactable":true,"interactions":["grab","tap"]}}`,
  `{"v":"1.0.0","id":"c1","type":"client.ack","ts":5,"session":"S","reply_to":"b3","payload":{}}`,
];

describe("PROTOCOL.md §7 reference example", () => {
  it("every line decodes and validates", () => {
    for (const line of REFERENCE) {
      const env = decode(line);
      expect(env.v).toBe("1.0.0");
      expect(env.session).toBe("S");
      expect(isValid(line, { allowUnknownTypes: false })).toBe(true);
      validate(line); // throws on violation
    }
  });

  it("the holo.spawn payload has the expected shape", () => {
    const env = decode<HoloObject>(REFERENCE[3]!);
    expect(env.payload.object_id).toBe("O1");
    expect(env.payload.widget_type).toBe("weather_orb");
    expect(env.payload.transform.anchor).toBe("head");
    expect(env.payload.transform.billboard).toBe(true);
    expect(env.payload.props?.city).toBe("Tokyo");
  });

  it("the ack correlates via reply_to", () => {
    const env = decode(REFERENCE[4]!);
    expect(env.type).toBe("client.ack");
    expect(env.reply_to).toBe("b3");
    expect(env.payload).toEqual({});
  });
});
