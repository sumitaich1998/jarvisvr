import { describe, expect, it } from "vitest";
import {
  type AgentObservation,
  type AudioEvent,
  type AudioScene,
  type Gaze,
  MessageType,
  PROTOCOL_VERSION,
  type PerceptionRequest,
  type PerceptionState,
  type SceneObjects,
  SUPPORTED_VERSIONS,
  type VisionFrame,
  decode,
  encode,
  isValid,
  iterErrors,
  newMessage,
  validate,
} from "../src/index.js";

const cases: Array<[string, Record<string, unknown>]> = [
  [
    MessageType.PERCEPTION_VISION_FRAME,
    {
      frame_id: "F1",
      camera: "rgb_center",
      format: "jpeg",
      width: 1024,
      height: 1024,
      quality: 70,
      transport: "inline",
      data: "/9j/4AAQ",
      seq: 1,
      ts_capture: 2,
      pose: { position: [0, 1.6, 0], rotation: [0, 0, 0, 1] },
      intrinsics: { fx: 720, fy: 720, cx: 512, cy: 512 },
    } satisfies VisionFrame,
  ],
  [MessageType.PERCEPTION_AUDIO_EVENT, { label: "doorbell", confidence: 0.82, ts: 10, loudness_db: -22 } satisfies AudioEvent],
  [
    MessageType.PERCEPTION_AUDIO_SCENE,
    { ambient_transcript: "overheard", speaker: "other", sounds: [{ label: "music", confidence: 0.6 }], loudness_db: -30, window_ms: 4000 } satisfies AudioScene,
  ],
  [
    MessageType.PERCEPTION_GAZE,
    { source: "eyes", origin: [0, 1.6, 0], direction: [0, 0, 1], hit_object_id: null, hit_point: [0.2, 1.3, 0.9], dwell_ms: 600 } satisfies Gaze,
  ],
  [
    MessageType.PERCEPTION_SCENE_OBJECTS,
    { objects: [{ label: "coffee mug", confidence: 0.78, bbox: [120, 80, 64, 64], position: [0.3, 0.8, 0.7], anchor: "world" }] } satisfies SceneObjects,
  ],
  [
    MessageType.PERCEPTION_STATE,
    {
      vision: { active: true, fps: 2, resolution: "1024x1024", camera: "rgb_center" },
      ambient_audio: { active: true },
      gaze: { active: false },
      thermal: "nominal",
      battery: 0.74,
    } satisfies PerceptionState,
  ],
  [MessageType.PERCEPTION_REQUEST, { stream: "vision", action: "start", fps: 2, reason: "user asked" } satisfies PerceptionRequest],
  [
    MessageType.AGENT_OBSERVATION,
    { text: "I can see a coffee mug.", final: true, annotations: [{ label: "coffee mug", object_id: "O9", position: [0.3, 0.8, 0.7], anchor: "world" }] } satisfies AgentObservation,
  ],
];

describe("v1.1 perception round-trip", () => {
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

  it("rejects malformed perception messages", () => {
    expect(isValid({ v: "1.1.0", id: "x", type: "perception.vision_frame", ts: 1, payload: { frame_id: "F1", format: "jpeg" } })).toBe(false);
    expect(isValid({ v: "1.1.0", id: "x", type: "perception.request", ts: 1, payload: { stream: "vision" } })).toBe(false);
    expect(isValid({ v: "1.1.0", id: "x", type: "perception.request", ts: 1, payload: { stream: "smell", action: "start" } })).toBe(false);
    expect(isValid({ v: "1.1.0", id: "x", type: "agent.observation", ts: 1, payload: { final: true } })).toBe(false);
  });

  it("exposes the bumped version + supported versions", () => {
    expect(PROTOCOL_VERSION).toBe("1.3.0");
    expect(SUPPORTED_VERSIONS).toContain("1.0.0");
    expect(SUPPORTED_VERSIONS).toContain("1.1.0");
  });
});

// Verbatim from PROTOCOL.md §8.6
const REFERENCE_8_6: string[] = [
  `{"v":"1.1.0","id":"r1","type":"perception.request","ts":1,"session":"S","payload":{"stream":"vision","action":"start","fps":2,"reason":"user asked what they're looking at"}}`,
  `{"v":"1.1.0","id":"f1","type":"perception.vision_frame","ts":2,"session":"S","payload":{"frame_id":"F1","camera":"rgb_center","format":"jpeg","width":1024,"height":1024,"transport":"inline","data":"/9j/4AAQ…","seq":1,"ts_capture":2,"pose":{"position":[0,1.6,0],"rotation":[0,0,0,1]}}}`,
  `{"v":"1.1.0","id":"u1","type":"user.voice_transcript","ts":3,"session":"S","payload":{"text":"hey jarvis, what is this on my desk?","attach_perception":true}}`,
  `{"v":"1.1.0","id":"o1","type":"agent.observation","ts":4,"session":"S","payload":{"text":"That's a ceramic coffee mug.","final":true,"annotations":[{"label":"coffee mug","position":[0.3,0.8,0.7],"anchor":"world"}]}}`,
  `{"v":"1.1.0","id":"o2","type":"holo.spawn","ts":5,"session":"S","payload":{"object_id":"O9","widget_type":"vision_annotation","transform":{"anchor":"world","position":[0.3,0.95,0.7],"rotation":[0,0,0,1],"scale":[1,1,1],"billboard":true},"props":{"label":"coffee mug","confidence":0.78},"interactable":true,"interactions":["tap"]}}`,
  `{"v":"1.1.0","id":"o3","type":"agent.speech","ts":6,"session":"S","payload":{"text":"Looks like your coffee mug — want me to set a reminder to refill it?","final":true}}`,
  `{"v":"1.1.0","id":"r2","type":"perception.request","ts":7,"session":"S","payload":{"stream":"vision","action":"stop"}}`,
];

describe("PROTOCOL.md §8.6 multimodal turn", () => {
  it("every line decodes and validates", () => {
    for (const line of REFERENCE_8_6) {
      const env = decode(line);
      expect(env.v).toBe("1.1.0");
      expect(isValid(line, { allowUnknownTypes: false })).toBe(true);
      validate(line);
    }
  });

  it("the vision_frame + observation decode with the right shape", () => {
    const f1 = decode<VisionFrame>(REFERENCE_8_6[1]!);
    expect(f1.payload.transport).toBe("inline");
    expect(f1.payload.camera).toBe("rgb_center");
    const o1 = decode<AgentObservation>(REFERENCE_8_6[3]!);
    expect(o1.payload.annotations?.[0]?.label).toBe("coffee mug");
  });

  it("still accepts a v1.0.0 frame (backward compatible)", () => {
    expect(isValid(`{"v":"1.0.0","id":"a","type":"agent.speech","ts":1,"session":"S","payload":{"text":"hi","final":true}}`, { allowUnknownTypes: false })).toBe(true);
  });
});
