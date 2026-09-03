/// <reference types="vitest/config" />

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export function resolveBasePath(
  environment: Readonly<Record<string, string | undefined>> = process.env,
): string {
  return environment.VITE_BASE_PATH ?? "/";
}

export default defineConfig({
  base: resolveBasePath(),
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
});
