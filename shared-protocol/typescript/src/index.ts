/**
 * @jarvisvr/protocol — TypeScript bindings for the JarvisVR wire protocol (v1).
 *
 * The JSON Schemas in `shared-protocol/schema` are the source of truth; this
 * package provides typed builders plus `encode`, `decode`, `newMessage`, and an
 * Ajv-backed `validate` built on top of them.
 */
export { PROTOCOL_VERSION, SUPPORTED_VERSIONS } from "./version.js";
export {
  KNOWN_TYPES,
  MessageType,
  type MessageTypeName,
  TYPE_TO_SCHEMA,
} from "./catalog.js";
export * from "./types.js";
export {
  SCHEMA_DIR,
  ajv,
  envelopeValidator,
  loadSchemas,
  payloadValidator,
  type ErrorObject,
  type ValidateFunction,
} from "./schemas.js";
export {
  type MessageInput,
  type NewMessageOptions,
  ProtocolValidationError,
  type ValidateOptions,
  decode,
  encode,
  isValid,
  iterErrors,
  newId,
  newMessage,
  nowMs,
  validate,
} from "./codec.js";
