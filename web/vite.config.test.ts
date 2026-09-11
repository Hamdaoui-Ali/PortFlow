import { describe, expect, it } from "vitest";

import { resolveBasePath, resolveLocalApiTarget } from "./vite.config";

describe("Pages base path", () => {
  it("uses the repository path supplied by deployment", () => {
    expect(resolveBasePath({ VITE_BASE_PATH: "/PortFlow/" })).toBe("/PortFlow/");
  });

  it("keeps root-relative paths for local development", () => {
    expect(resolveBasePath({})).toBe("/");
  });

  it("keeps the local API on loopback by default", () => {
    expect(resolveLocalApiTarget({})).toBe("http://127.0.0.1:8000");
  });

  it("allows a local developer to override the API port", () => {
    expect(resolveLocalApiTarget({ PORTFLOW_LOCAL_API_TARGET: "http://127.0.0.1:8010" }))
      .toBe("http://127.0.0.1:8010");
  });
});
