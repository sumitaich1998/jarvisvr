/** Encode / decode / construct / validate JarvisVR protocol messages. */
import { randomUUID } from "node:crypto";
import { type ErrorObject, envelopeValidator, payloadValidator } from "./schemas.js";
import type { Envelope, Json } from "./types.js";
import { PROTOCOL_VERSION } from "./version.js";

export type MessageInput = Envelope | Json | string | Uint8Array;

export interface ValidateOptions {
  /** Tolerate unknown message types (PROTOCOL.md §2). Default: true. */
  allowUnknownTypes?: boolean;
}

export interface NewMessageOptions {
  replyTo?: string;
  id?: string;
  ts?: number;
}

export class ProtocolValidationError extends Error {
  readonly errors: string[];

  constructor(errors: string[]) {
    super(errors.length ? errors.join("; ") : "invalid message");
    this.name = "ProtocolValidationError";
    this.errors = errors;
  }
}

export function nowMs(): number {
  return Date.now();
}

export function newId(): string {
  return randomUUID();
}

/** Build an envelope with a fresh uuid `id` and epoch-ms `ts`. */
export function newMessage<P = Json>(
  type: string,
  payload?: P,
  session?: string,
  opts: NewMessageOptions = {},
): Envelope<P> {
  const env: Envelope<P> = {
    v: PROTOCOL_VERSION,
    id: opts.id ?? newId(),
    type,
    ts: opts.ts ?? nowMs(),
    payload: (payload ?? ({} as P)),
  };
  if (session !== undefined) env.session = session;
  if (opts.replyTo !== undefined) env.reply_to = opts.replyTo;
  return env;
}

/** Serialize a message to a compact JSON text frame (undefined fields omitted). */
export function encode(msg: Envelope | Json): string {
  return JSON.stringify(msg);
}

/** Parse a JSON text frame (or bytes) into an Envelope. */
export function decode<P = Json>(data: string | Uint8Array): Envelope<P> {
  const text = typeof data === "string" ? data : new TextDecoder().decode(data);
  return JSON.parse(text) as Envelope<P>;
}

function toDoc(msg: MessageInput): Json {
  if (typeof msg === "string") return JSON.parse(msg) as Json;
  if (msg instanceof Uint8Array) return JSON.parse(new TextDecoder().decode(msg)) as Json;
  return msg as Json;
}

/** Format Ajv errors into human-readable strings. Exported for direct testing
 * (not re-exported from the package index). */
export function formatErrors(prefix: string, errors: ErrorObject[] | null | undefined): string[] {
  if (!errors) return [];
  return errors.map((e) => `${prefix} ${e.instancePath || "<root>"}: ${e.message ?? "invalid"}`);
}

/** Return a list of human-readable schema violations (empty == valid). */
export function iterErrors(msg: MessageInput, opts: ValidateOptions = {}): string[] {
  const allowUnknown = opts.allowUnknownTypes ?? true;
  const doc = toDoc(msg);
  const errors: string[] = [];

  const env = envelopeValidator();
  if (!env(doc)) errors.push(...formatErrors("envelope", env.errors));

  const type = (doc as { type?: unknown }).type;
  const payload = (doc as { payload?: unknown }).payload ?? {};
  if (typeof type === "string") {
    const pv = payloadValidator(type);
    if (!pv) {
      // pv is null exactly for types not in TYPE_TO_SCHEMA (unknown types).
      if (!allowUnknown) {
        errors.push(`unknown message type: ${JSON.stringify(type)}`);
      }
    } else if (typeof payload !== "object" || Array.isArray(payload)) {
      // payload is never null here (`?? {}` above); reject non-object payloads.
      errors.push("payload: must be an object");
    } else if (!pv(payload)) {
      errors.push(...formatErrors(`${type} payload`, pv.errors));
    }
  }
  return errors;
}

/** Validate a message; returns the normalized doc or throws ProtocolValidationError. */
export function validate(msg: MessageInput, opts: ValidateOptions = {}): Json {
  const errors = iterErrors(msg, opts);
  if (errors.length) throw new ProtocolValidationError(errors);
  return toDoc(msg);
}

export function isValid(msg: MessageInput, opts: ValidateOptions = {}): boolean {
  return iterErrors(msg, opts).length === 0;
}
