/// <reference types="vitest/config" />

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export function resolveBasePath(
  environment: Readonly<Record<string, string | undefined>> = process.env,
): string {
  return environment.VITE_BASE_PATH ?? "/";
}

const defaultTestExclude = [
  "**/node_modules/**",
  "**/dist/**",
  "**/.{idea,git,cache,output,temp}/**",
];

export default defineConfig({
  base: resolveBasePath(),
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    exclude: process.env.PORTFLOW_FAILURE_TESTS || process.env.PORTFLOW_RECONCILIATION_DIR
      ? defaultTestExclude
      : [...defaultTestExclude, "e2e/reconciliation.spec.tsx", "e2e/failure-states.spec.tsx"],
  },
});
