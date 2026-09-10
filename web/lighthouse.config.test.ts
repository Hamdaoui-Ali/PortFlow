import { describe, expect, it } from "vitest";

import { createLighthouseConfig } from "./lighthouse.config.js";

describe("Lighthouse configuration", () => {
  it("audits a Pages build through its configured base path", () => {
    const config = createLighthouseConfig({
      PORTFLOW_LIGHTHOUSE_PORT: "4173",
      PORTFLOW_LIGHTHOUSE_PROFILE_DIR: "C:/tmp/portflow-lighthouse-profile",
      VITE_BASE_PATH: "/PortFlow/",
    });

    expect(config.collect.url).toEqual(["http://127.0.0.1:4173/PortFlow/"]);
    expect(config.collect.startServerCommand).toBe("node scripts/lighthouse-server.mjs");
    expect(config.collect.startServerReadyPattern).toBe("PortFlow Lighthouse server listening");
    expect(config.collect.staticDistDir).toBeUndefined();
    expect(config.collect.puppeteerScript).toBe("scripts/lighthouse-puppeteer.cjs");
    expect(config.collect.puppeteerLaunchOptions).toEqual({
      userDataDir: "C:/tmp/portflow-lighthouse-profile",
      args: ["--no-sandbox"],
    });
    expect(config.assert.aggregationMethod).toBe("median-run");
  });

  it("keeps the local audit at the root when no Pages base path is supplied", () => {
    const config = createLighthouseConfig({ PORTFLOW_LIGHTHOUSE_PORT: "4173" });

    expect(config.collect.url).toEqual(["http://127.0.0.1:4173/"]);
  });
});
