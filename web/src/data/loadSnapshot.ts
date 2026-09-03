import { manifestSchema, overviewSchema, replaySchema, type SnapshotV1 } from "./schema";
import { SnapshotLoadError } from "./errors";

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
  let manifestResponse: Response;
  try {
    manifestResponse = await fetcher(`${dataBase}manifest.json`, { cache: "no-cache" });
  } catch {
    throw new SnapshotLoadError("unavailable");
  }
  const manifestResult = manifestSchema.safeParse(
    await readJsonOrUnavailable(manifestResponse, "Manifest"),
  );
  if (!manifestResult.success) {
    throw new SnapshotLoadError("malformed", "Manifest did not match schema version 1");
  }

  let overviewResponse: Response;
  try {
    overviewResponse = await fetcher(`${dataBase}${manifestResult.data.datasets.overview.path}`);
  } catch {
    throw new SnapshotLoadError("unavailable");
  }
  const overviewResult = overviewSchema.safeParse(
    await readJsonOrUnavailable(overviewResponse, "Overview dataset"),
  );
  if (!overviewResult.success) {
    throw new SnapshotLoadError("malformed", "Overview dataset did not match schema version 1");
  }
  if (overviewResult.data.availability.scheduled_intervals === 0) {
    throw new SnapshotLoadError("empty");
  }

  const replayEntry = manifestResult.data.datasets.event_replay;
  if (!replayEntry) {
    return { manifest: manifestResult.data, overview: overviewResult.data };
  }

  try {
    const replayResponse = await fetcher(`${dataBase}${replayEntry.path}`);
    const replayResult = replaySchema.safeParse(
      await readJson(replayResponse, "Event replay dataset"),
    );
    return replayResult.success
      ? { manifest: manifestResult.data, overview: overviewResult.data, event_replay: replayResult.data }
      : { manifest: manifestResult.data, overview: overviewResult.data };
  } catch {
    return { manifest: manifestResult.data, overview: overviewResult.data };
  }
}

async function readJsonOrUnavailable(response: Response, label: string): Promise<unknown> {
  try {
    return await readJson(response, label);
  } catch {
    throw new SnapshotLoadError("unavailable");
  }
}
