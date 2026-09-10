import { createServer } from "node:http";
import { readFile, stat } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { promisify } from "node:util";
import { gzip as gzipCallback } from "node:zlib";

const gzip = promisify(gzipCallback);

const contentTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".woff2": "font/woff2",
};

export function normalizeBasePath(basePath = "/") {
  const withLeadingSlash = basePath.startsWith("/") ? basePath : `/${basePath}`;
  return withLeadingSlash.endsWith("/") ? withLeadingSlash : `${withLeadingSlash}/`;
}

function send(response, statusCode, body = "") {
  response.statusCode = statusCode;
  response.setHeader("content-type", "text/plain; charset=utf-8");
  response.end(body);
}

function safePath(rootDir, relativePath) {
  const root = path.resolve(rootDir);
  const candidate = path.resolve(root, relativePath);
  if (candidate !== root && !candidate.startsWith(`${root}${path.sep}`)) {
    return undefined;
  }
  return candidate;
}

function isCompressible(filePath) {
  return [".css", ".html", ".js", ".json", ".svg"].includes(path.extname(filePath));
}

async function resolveFile(rootDir, relativePath) {
  const candidate = safePath(rootDir, relativePath);
  if (!candidate) return undefined;

  try {
    const candidateStats = await stat(candidate);
    if (candidateStats.isFile()) return candidate;
    if (candidateStats.isDirectory()) {
      const indexPath = path.join(candidate, "index.html");
      const indexStats = await stat(indexPath);
      return indexStats.isFile() ? indexPath : undefined;
    }
    return undefined;
  } catch {
    if (path.extname(relativePath)) return undefined;
    return resolveFile(rootDir, "index.html");
  }
}

export function createLighthouseRequestHandler({ rootDir, basePath = "/" }) {
  const normalizedBasePath = normalizeBasePath(basePath);

  return async function handleRequest(request, response) {
    if (request.method !== "GET" && request.method !== "HEAD") {
      response.setHeader("allow", "GET, HEAD");
      send(response, 405, "Method Not Allowed");
      return;
    }

    let pathname;
    try {
      pathname = decodeURIComponent(new URL(request.url ?? "/", "http://localhost").pathname);
    } catch {
      send(response, 400, "Bad Request");
      return;
    }

    if (!pathname.startsWith(normalizedBasePath)) {
      send(response, 404, "Not Found");
      return;
    }

    const relativePath = pathname.slice(normalizedBasePath.length) || "index.html";
    const filePath = await resolveFile(rootDir, relativePath);
    if (!filePath) {
      send(response, 404, "Not Found");
      return;
    }

    try {
      let body = await readFile(filePath);
      const acceptsGzip = String(request.headers["accept-encoding"] ?? "").includes("gzip");
      const shouldCompress = acceptsGzip && isCompressible(filePath);
      if (shouldCompress) {
        body = await gzip(body);
        response.setHeader("content-encoding", "gzip");
        response.setHeader("vary", "accept-encoding");
      }
      response.statusCode = 200;
      response.setHeader(
        "content-type",
        contentTypes[path.extname(filePath)] ?? "application/octet-stream",
      );
      response.setHeader("content-length", body.byteLength);
      response.end(request.method === "HEAD" ? undefined : body);
    } catch {
      send(response, 404, "Not Found");
    }
  };
}

export async function createLighthouseServer({
  rootDir,
  basePath = "/",
  host = "127.0.0.1",
  port = 0,
}) {
  const handleRequest = createLighthouseRequestHandler({ basePath, rootDir });
  const server = createServer((request, response) => {
    void handleRequest(request, response).catch(() => {
      if (!response.headersSent) send(response, 500, "Internal Server Error");
      else response.destroy();
    });
  });

  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, host, resolve);
  });

  const address = server.address();
  if (!address || typeof address === "string") {
    await new Promise((resolve) => server.close(resolve));
    throw new Error("Lighthouse server did not expose a TCP port");
  }

  return {
    port: address.port,
    close: () => new Promise((resolve, reject) => {
      server.close((error) => (error ? reject(error) : resolve()));
    }),
  };
}

const entryPoint = process.argv[1] ? pathToFileURL(path.resolve(process.argv[1])).href : undefined;
if (entryPoint === import.meta.url) {
  createLighthouseServer({
    basePath: process.env.VITE_BASE_PATH ?? "/",
    host: "127.0.0.1",
    port: Number.parseInt(process.env.PORTFLOW_LIGHTHOUSE_PORT ?? "4173", 10),
    rootDir: path.resolve(process.cwd(), "dist"),
  }).then(({ port }) => {
    console.log(`PortFlow Lighthouse server listening on ${port}`);
  }).catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
}
