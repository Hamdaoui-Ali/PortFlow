import {
  equipmentSchema,
  incidentsSchema,
  manifestSchema,
  overviewSchema,
  qualitySchema,
  replaySchema,
  type EquipmentDatasetState,
  type IncidentDatasetState,
  type QualityDatasetState,
  type SnapshotV1,
} from "./schema";
import { SnapshotLoadError } from "./errors";

export const OPTIONAL_DATASET_TIMEOUT_MS = 5000;

function withTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timeoutId = setTimeout(() => reject(new Error("Optional dataset timed out")), timeoutMs);
    promise.then(
      (value) => {
        clearTimeout(timeoutId);
        resolve(value);
      },
      (error: unknown) => {
        clearTimeout(timeoutId);
        reject(error);
      },
    );
  });
}

async function loadEquipmentDataset(
  fetcher: SnapshotFetch,
  url: string,
): Promise<EquipmentDatasetState> {
  let response: Response;
  try {
    response = await fetcher(url);
  } catch {
    return { status: "unavailable" };
  }
  if (!response.ok) {
    return { status: "unavailable" };
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return { status: "malformed" };
  }
  const result = equipmentSchema.safeParse(payload);
  if (!result.success) {
    return { status: "malformed" };
  }
  return result.data.length === 0
    ? { status: "empty" }
    : { status: "ready", records: result.data };
}

async function loadIncidentDataset(
  fetcher: SnapshotFetch,
  url: string,
): Promise<IncidentDatasetState> {
  let response: Response;
  try {
    response = await fetcher(url);
  } catch {
    return { status: "unavailable" };
  }
  if (!response.ok) return { status: "unavailable" };

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return { status: "malformed" };
  }
  const result = incidentsSchema.safeParse(payload);
  if (!result.success) return { status: "malformed" };
  return result.data.length === 0
    ? { status: "empty" }
    : { status: "ready", records: result.data };
}

async function loadQualityDataset(
  fetcher: SnapshotFetch,
  url: string,
): Promise<QualityDatasetState> {
  let response: Response;
  try {
    response = await fetcher(url);
  } catch {
    return { status: "unavailable" };
  }
  if (!response.ok) return { status: "unavailable" };

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return { status: "malformed" };
  }
  if (Array.isArray(payload) && payload.length === 0) return { status: "empty" };
  const result = qualitySchema.safeParse(payload);
  return result.success ? { status: "ready", data: result.data } : { status: "malformed" };
}

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

  const equipmentEntry = manifestResult.data.datasets.equipment;
  const incidentsEntry = manifestResult.data.datasets.incidents;
  const qualityEntry = manifestResult.data.datasets.quality;
  const equipmentPromise = equipmentEntry
    ? withTimeout(loadEquipmentDataset(fetcher, `${dataBase}${equipmentEntry.path}`), OPTIONAL_DATASET_TIMEOUT_MS)
        .catch(() => ({ status: "unavailable" } as const))
    : Promise.resolve({ status: "absent" } as const);
  const incidentsPromise = incidentsEntry
    ? withTimeout(loadIncidentDataset(fetcher, `${dataBase}${incidentsEntry.path}`), OPTIONAL_DATASET_TIMEOUT_MS)
        .catch(() => ({ status: "unavailable" } as const))
    : Promise.resolve({ status: "absent" } as const);
  const qualityPromise = qualityEntry
    ? withTimeout(loadQualityDataset(fetcher, `${dataBase}${qualityEntry.path}`), OPTIONAL_DATASET_TIMEOUT_MS)
        .catch(() => ({ status: "unavailable" } as const))
    : Promise.resolve({ status: "absent" } as const);
  const [equipment, incidents, quality] = await Promise.all([
    equipmentPromise,
    incidentsPromise,
    qualityPromise,
  ]);

  const replayEntry = manifestResult.data.datasets.event_replay;
  if (!replayEntry) {
    return { manifest: manifestResult.data, overview: overviewResult.data, equipment, incidents, quality };
  }

  try {
    const replayResponse = await fetcher(`${dataBase}${replayEntry.path}`);
    const replayResult = replaySchema.safeParse(
      await readJson(replayResponse, "Event replay dataset"),
    );
    return replayResult.success
      ? { manifest: manifestResult.data, overview: overviewResult.data, event_replay: replayResult.data, equipment, incidents, quality }
      : { manifest: manifestResult.data, overview: overviewResult.data, equipment, incidents, quality };
  } catch {
    return { manifest: manifestResult.data, overview: overviewResult.data, equipment, incidents, quality };
  }
}

async function readJsonOrUnavailable(response: Response, label: string): Promise<unknown> {
  try {
    return await readJson(response, label);
  } catch {
    throw new SnapshotLoadError("unavailable");
  }
}
