import { describe, expect, it } from "vitest";

import { resolveBasePath } from "./vite.config";

describe("Pages base path", () => {
  it("uses the repository path supplied by deployment", () => {
    expect(resolveBasePath({ VITE_BASE_PATH: "/PortFlow/" })).toBe("/PortFlow/");
  });

  it("keeps root-relative paths for local development", () => {
    expect(resolveBasePath({})).toBe("/");
  });
});
