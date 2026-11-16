import { defineConfig } from "vitest/config";

export default defineConfig({ test: { include: ["test/regression/**/*.spec.ts"] } });
