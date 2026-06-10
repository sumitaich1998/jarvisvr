/**
 * Loads the canonical JSON Schemas and builds Ajv (draft 2020-12) validators.
 *
 * The schemas in `shared-protocol/schema` are the single source of truth. We
 * locate that directory (env override or upward search), register every schema
 * by `$id` so cross-file `$ref`s resolve, and expose cached validators.
 */
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { Ajv2020, type ErrorObject, type ValidateFunction } from "ajv/dist/2020.js";
import { TYPE_TO_SCHEMA } from "./catalog.js";

/**
 * Locate the canonical schema directory. Exported (but not re-exported from the
 * package index) so tests can exercise the env / upward-search / not-found paths.
 * `opts.env` / `opts.startDir` override the defaults for testing.
 */
export function findSchemaDir(opts: { env?: string; startDir?: string } = {}): string {
  const candidates: string[] = [];
  const env = opts.env ?? process.env.JARVIS_PROTOCOL_SCHEMA_DIR;
  if (env) candidates.push(env);
  let dir = opts.startDir ?? dirname(fileURLToPath(import.meta.url));
  for (;;) {
    candidates.push(join(dir, "schema"));
    const parent = dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  for (const cand of candidates) {
    if (existsSync(join(cand, "envelope.schema.json"))) return cand;
  }
  throw new Error(
    "Could not locate shared-protocol/schema. Set JARVIS_PROTOCOL_SCHEMA_DIR to its path.",
  );
}

/** Absolute path to the canonical schema directory. */
export const SCHEMA_DIR = findSchemaDir();

let _schemas: Record<string, Record<string, unknown>> | null = null;

/** Return `{ filename: schema }` for every `*.schema.json` in SCHEMA_DIR. */
export function loadSchemas(): Record<string, Record<string, unknown>> {
  if (_schemas) return _schemas;
  const out: Record<string, Record<string, unknown>> = {};
  for (const file of readdirSync(SCHEMA_DIR)) {
    if (file.endsWith(".schema.json")) {
      out[file] = JSON.parse(readFileSync(join(SCHEMA_DIR, file), "utf-8"));
    }
  }
  _schemas = out;
  return out;
}

let _ajv: Ajv2020 | null = null;

export function ajv(): Ajv2020 {
  if (_ajv) return _ajv;
  const instance = new Ajv2020({ allErrors: true, strict: false });
  for (const schema of Object.values(loadSchemas())) {
    instance.addSchema(schema);
  }
  _ajv = instance;
  return instance;
}

export function envelopeValidator(): ValidateFunction {
  const fn = ajv().getSchema("https://jarvisvr.dev/schema/envelope.schema.json");
  /* c8 ignore next -- defensive: the envelope schema is always registered */
  if (!fn) throw new Error("envelope schema not registered");
  return fn;
}

export function payloadValidator(type: string): ValidateFunction | null {
  const file = TYPE_TO_SCHEMA[type];
  if (!file) return null;
  const schema = loadSchemas()[file];
  const id = schema["$id"] as string;
  /* c8 ignore next -- getSchema always resolves a registered $id for a known type */
  return ajv().getSchema(id) ?? null;
}

export type { ErrorObject, ValidateFunction };
