import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: ["test/**/*.test.ts"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.ts"],
      // index.ts is a pure re-export barrel; types.ts is type-only (erased at
      // runtime). Both have no executable logic to test.
      exclude: ["src/index.ts", "src/types.ts"],
      reporter: ["text", "text-summary"],
      all: true,
      thresholds: {
        lines: 100,
        functions: 100,
        statements: 100,
        branches: 100,
      },
    },
  },
});
