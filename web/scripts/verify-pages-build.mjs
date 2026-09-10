import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

function normalizeBasePath(basePath) {
  const withLeadingSlash = basePath.startsWith("/") ? basePath : `/${basePath}`;
  return withLeadingSlash.endsWith("/") ? withLeadingSlash : `${withLeadingSlash}/`;
}

export async function verifyPagesBuild(distRoot, basePath = "/PortFlow/") {
  const normalizedBasePath = normalizeBasePath(basePath);
  const assetsPath = `${normalizedBasePath}assets/`;
  const dataPath = `${normalizedBasePath}data/`;
  const distUrl = typeof distRoot === "string"
    ? pathToFileURL(path.resolve(distRoot) + path.sep)
    : distRoot;
  const index = await readFile(new URL("index.html", distUrl), "utf8");

  if (!index.includes(`src="${assetsPath}`)) {
    throw new Error(`Pages build does not reference JavaScript under ${assetsPath}`);
  }
  if (!index.includes(`href="${assetsPath}`)) {
    throw new Error(`Pages build does not reference CSS under ${assetsPath}`);
  }

  const scriptPath = index.match(/src="([^"]+\.js)"/)?.[1];
  if (!scriptPath) {
    throw new Error("Pages build does not contain a JavaScript entry point");
  }

  const scriptName = scriptPath.split("/").at(-1);
  if (!scriptName) {
    throw new Error("Pages build entry point has no filename");
  }
  await readFile(new URL(`assets/${scriptName}`, distUrl), "utf8");

  const assetUrl = new URL("assets/", distUrl);
  const scriptNames = (await readdir(assetUrl)).filter((name) => name.endsWith(".js"));
  const scripts = await Promise.all(
    scriptNames.map((name) => readFile(new URL(name, assetUrl), "utf8")),
  );
  const hasDataLoader = scripts.some((script) => (
    script.includes(normalizedBasePath)
    && script.includes("data/")
    && script.includes("manifest.json")
  ));
  if (!hasDataLoader) {
    throw new Error(`Pages JavaScript does not construct the ${dataPath}manifest.json request`);
  }
}

const entryPoint = process.argv[1]
  ? pathToFileURL(path.resolve(process.argv[1])).href
  : undefined;

if (entryPoint === import.meta.url) {
  verifyPagesBuild(new URL("../dist/", import.meta.url))
    .then(() => console.log("Verified /PortFlow/ asset and data paths."))
    .catch((error) => {
      console.error(error);
      process.exitCode = 1;
    });
}
