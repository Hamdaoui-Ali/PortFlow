/// <reference types="vitest/config" />

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export function resolveBasePath(
  environment: Readonly<Record<string, string | undefined>> = process.env,
): string {
  return environment.VITE_BASE_PATH ?? "/";
}

export function resolveLocalApiTarget(
  environment: Readonly<Record<string, string | undefined>> = process.env,
): string {
  return environment.PORTFLOW_LOCAL_API_TARGET ?? "http://127.0.0.1:8000";
}

const defaultTestExclude = [
  "**/node_modules/**",
  "**/dist/**",
  "**/.{idea,git,cache,output,temp}/**",
];

const failureTestsEnabled = process.env.PORTFLOW_FAILURE_TESTS === "1";
const reconciliationTestsEnabled = Boolean(process.env.PORTFLOW_RECONCILIATION_DIR);
const suiteExcludes = [
  ...(failureTestsEnabled ? [] : ["e2e/failure-states.spec.tsx"]),
  ...(reconciliationTestsEnabled ? [] : ["e2e/reconciliation.spec.tsx"]),
];

export default defineConfig({
  base: resolveBasePath(),
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: resolveLocalApiTarget(),
        changeOrigin: false,
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    exclude: [...defaultTestExclude, ...suiteExcludes],
  },
});
