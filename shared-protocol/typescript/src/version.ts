/** Wire-protocol version implemented by these bindings (mirrors PROTOCOL.md). */
export const PROTOCOL_VERSION = "1.3.0" as const;

/** Protocol versions accepted on the wire (v1.3 still serves v1.0–v1.2 clients). */
export const SUPPORTED_VERSIONS = ["1.0.0", "1.1.0", "1.2.0", "1.3.0"] as const;
