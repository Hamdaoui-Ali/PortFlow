import { readFile } from "node:fs/promises";

const index = await readFile(new URL("../dist/index.html", import.meta.url), "utf8");
if (!index.includes('src="/PortFlow/assets/')) {
  throw new Error("Pages build does not reference JavaScript under /PortFlow/assets/");
}
if (!index.includes('href="/PortFlow/assets/')) {
  throw new Error("Pages build does not reference CSS under /PortFlow/assets/");
}

const scriptPath = index.match(/src="([^"]+\.js)"/)?.[1];
if (!scriptPath) {
  throw new Error("Pages build does not contain a JavaScript entry point");
}

const scriptName = scriptPath.split("/").at(-1);
const script = await readFile(new URL("../dist/assets/" + scriptName, import.meta.url), "utf8");
if (
  !script.includes("/PortFlow/") ||
  !script.includes("data/") ||
  !script.includes("manifest.json")
) {
  throw new Error("Pages JavaScript does not construct the /PortFlow/data/ manifest request");
}

console.log("Verified /PortFlow/ asset and data paths.");
