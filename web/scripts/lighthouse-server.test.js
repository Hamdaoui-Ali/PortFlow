import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";

import { createLighthouseServer } from "./lighthouse-server.mjs";

const runningServers = [];

afterEach(async () => {
  await Promise.all(runningServers.splice(0).map((server) => server.close()));
});

describe("Lighthouse static server", () => {
  it("serves the build and its assets below the Pages base path", async () => {
    const rootDir = await mkdtemp(path.join(os.tmpdir(), "portflow-lighthouse-"));
    await mkdir(path.join(rootDir, "assets"));
    await writeFile(
      path.join(rootDir, "index.html"),
      '<script type="module" src="/PortFlow/assets/app.js"></script>',
      "utf8",
    );
    await writeFile(path.join(rootDir, "assets", "app.js"), "console.log('ok');", "utf8");

    const server = await createLighthouseServer({
      basePath: "/PortFlow/",
      port: 0,
      rootDir,
    });
    runningServers.push(server);

    try {
      const page = await fetch(`http://127.0.0.1:${server.port}/PortFlow/`);
      expect(page.status).toBe(200);
      expect(await page.text()).toContain("/PortFlow/assets/app.js");

      const asset = await fetch(`http://127.0.0.1:${server.port}/PortFlow/assets/app.js`);
      expect(asset.status).toBe(200);
      expect(await asset.text()).toContain("console.log");

      const compressedAsset = await fetch(`http://127.0.0.1:${server.port}/PortFlow/assets/app.js`, {
        headers: { "accept-encoding": "gzip" },
      });
      expect(compressedAsset.headers.get("content-encoding")).toBe("gzip");
      expect(compressedAsset.headers.get("vary")).toBe("accept-encoding");

      const unprefixedAsset = await fetch(`http://127.0.0.1:${server.port}/assets/app.js`);
      expect(unprefixedAsset.status).toBe(404);
    } finally {
      await rm(rootDir, { force: true, recursive: true });
    }
  });
});
