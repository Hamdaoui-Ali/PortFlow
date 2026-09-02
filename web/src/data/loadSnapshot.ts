import { manifestSchema, overviewSchema, type SnapshotV1 } from "./schema";

export type SnapshotFetch = (
  input: string | URL | Request,
  init?: RequestInit,
) => Promise<Response>;

async function readJson(response: Response, label: string): Promise<unknown> {
  if (!response.ok) {
    throw new Error(`${label} request failed with status ${response.status}`);
  }
  return response.json() as Promise<unknown>;
}

function withTrailingSlash(value: string): string {
  return value.endsWith("/") ? value : `${value}/`;
}

export async function loadSnapshot(
  fetcher: SnapshotFetch = fetch,
  baseUrl = import.meta.env.BASE_URL,
): Promise<SnapshotV1> {
  const dataBase = `${withTrailingSlash(baseUrl)}data/`;
  const manifestResponse = await fetcher(`${dataBase}manifest.json`, { cache: "no-cache" });
  const manifestResult = manifestSchema.safeParse(
    await readJson(manifestResponse, "Manifest"),
  );
  if (!manifestResult.success) {
    throw new Error("Manifest did not match schema version 1");
  }

  const overviewResponse = await fetcher(`${dataBase}${manifestResult.data.datasets.overview.path}`);
  const overviewResult = overviewSchema.safeParse(
    await readJson(overviewResponse, "Overview dataset"),
  );
  if (!overviewResult.success) {
    throw new Error("Overview dataset did not match schema version 1");
  }

  return { manifest: manifestResult.data, overview: overviewResult.data };
}
