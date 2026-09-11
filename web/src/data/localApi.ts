export type LocalColumnKind = "string" | "integer" | "number" | "boolean" | "date" | "datetime";

export interface LocalColumnSchema {
  name: string;
  kind: LocalColumnKind;
  required: boolean;
  nullable: boolean;
  description: string;
}

export interface LocalTableSchema {
  table_name: string;
  primary_key: string;
  columns: LocalColumnSchema[];
}

export interface LocalSchemaResponse {
  tables: LocalTableSchema[];
}

export interface LocalStatus {
  api: "ready";
  database: "connected" | "unavailable";
  schema: "ready" | "missing";
  pipeline: "idle" | "running" | "failed";
  message?: string;
}

export interface SeedResponse {
  seed: number;
  row_counts: Record<string, number>;
  digest_sha256: string;
}

export interface ImportPayload {
  table: string;
  records: Array<Record<string, unknown>>;
}

export interface ImportResponse {
  table_name: string;
  received_count: number;
  inserted_count: number;
  updated_count: number;
}

export interface RefreshResponse {
  manifest_path: string;
}

export type LocalApiResponseBody = Record<string, unknown>;
export type LocalApiFetcher = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>;

export class LocalApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, body: unknown) {
    const message = body && typeof body === "object" && "message" in body
      ? String(body.message)
      : `Local API request failed (${status})`;
    super(message);
    this.name = "LocalApiError";
    this.status = status;
    this.body = body;
  }
}

export interface LocalApiClient {
  getStatus(signal?: AbortSignal): Promise<LocalStatus>;
  getSchema(signal?: AbortSignal): Promise<LocalSchemaResponse>;
  seed(): Promise<SeedResponse>;
  importRecords(payload: ImportPayload): Promise<ImportResponse>;
  refresh(): Promise<RefreshResponse>;
}

function errorBodyFromText(text: string): unknown {
  if (!text) return {};
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return { error: "invalid_response", message: "Local API returned invalid JSON" };
  }
}

export function createLocalApi(
  baseUrl = "/api",
  fetcher: LocalApiFetcher = fetch,
): LocalApiClient {
  const normalizedBaseUrl = baseUrl.replace(/\/$/, "");

  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetcher(`${normalizedBaseUrl}${path}`, init);
    const body = errorBodyFromText(await response.text());
    if (!response.ok) {
      throw new LocalApiError(response.status, body);
    }
    return body as T;
  }

  const jsonPost = (path: string, body: unknown) => request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  return {
    getStatus: (signal) => request<LocalStatus>("/status", { method: "GET", signal }),
    getSchema: (signal) => request<LocalSchemaResponse>("/schema", { method: "GET", signal }),
    seed: () => jsonPost("/seed", {}) as Promise<SeedResponse>,
    importRecords: (payload) => jsonPost("/import", payload) as Promise<ImportResponse>,
    refresh: () => jsonPost("/refresh", {}) as Promise<RefreshResponse>,
  };
}
