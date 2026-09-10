import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";

import { verifyPagesBuild } from "./verify-pages-build.mjs";

const temporaryDirectories = [];

afterEach(async () => {
  await Promise.all(
    temporaryDirectories
      .splice(0)
      .map((directory) => rm(directory, { force: true, recursive: true })),
  );
});

describe("Pages build verification", () => {
  it("finds the data loader when it is emitted as a lazy JavaScript chunk", async () => {
    const distRoot = await mkdtemp(path.join(os.tmpdir(), "portflow-pages-"));
    temporaryDirectories.push(distRoot);
    await mkdir(path.join(distRoot, "assets"));
    await writeFile(
      path.join(distRoot, "index.html"),
      '<script type="module" src="/PortFlow/assets/index.js"></script><link rel="stylesheet" href="/PortFlow/assets/index.css">',
    );
    await writeFile(path.join(distRoot, "assets", "index.js"), "console.log('shell');");
    await writeFile(
      path.join(distRoot, "assets", "loadSnapshot.js"),
      'const manifestUrl = "/PortFlow/data/manifest.json"; export { manifestUrl };',
    );

    await expect(verifyPagesBuild(distRoot)).resolves.toBeUndefined();
  });
});
