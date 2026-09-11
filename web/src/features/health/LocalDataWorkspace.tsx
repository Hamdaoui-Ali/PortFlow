import { useCallback, useEffect, useMemo, useState, type ChangeEvent } from "react";

import {
  createLocalApi,
  LocalApiError,
  type ImportPayload,
  type LocalApiClient,
  type LocalColumnSchema,
  type LocalSchemaResponse,
  type LocalTableSchema,
} from "../../data/localApi";

interface LocalDataWorkspaceProps {
  api?: LocalApiClient;
  onSnapshotRefresh?: () => void;
}

type ConnectionState = "checking" | "unavailable" | "connected";

interface ImportIssueView {
  row_index: number;
  field?: string | null;
  code?: string;
  detail?: string;
}

const EXAMPLE_RECORDS: Record<string, Array<Record<string, unknown>>> = {
  terminals: [{
    terminal_id: "TM-101",
    name: "Local Terminal",
    timezone_name: "UTC",
    created_at: "2026-09-02T00:00:00Z",
    updated_at: "2026-09-02T00:00:02Z",
  }],
  incidents: [{
    incident_id: "inc-000101",
    equipment_id: "QC-001",
    severity: "MAJOR",
    status: "OPEN",
    opened_at: "2026-09-02T12:00:00Z",
    resolved_at: null,
    root_cause: "Hydraulic leak",
    created_at: "2026-09-02T12:00:00Z",
    updated_at: "2026-09-02T12:00:00Z",
  }],
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function exampleForTable(table: LocalTableSchema): Array<Record<string, unknown>> {
  const knownExample = EXAMPLE_RECORDS[table.table_name];
  if (knownExample) return knownExample;
  return [Object.fromEntries(table.columns.map((column) => [
    column.name,
    column.nullable ? null : placeholderValue(column),
  ]))];
}

function placeholderValue(column: LocalColumnSchema): unknown {
  if (column.kind === "boolean") return true;
  if (column.kind === "integer" || column.kind === "number") return 0;
  if (column.kind === "date") return "2026-09-02";
  if (column.kind === "datetime") return "2026-09-02T00:00:00Z";
  return column.name.endsWith("_id") ? "replace-me" : "value";
}

function formatCount(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

function readIssues(error: unknown): ImportIssueView[] {
  if (!(error instanceof LocalApiError) || !isRecord(error.body)) return [];
  const rawIssues = error.body.issues;
  if (!Array.isArray(rawIssues)) return [];
  return rawIssues.filter(isRecord).map((issue) => ({
    row_index: typeof issue.row_index === "number" ? issue.row_index : 0,
    field: typeof issue.field === "string" ? issue.field : null,
    code: typeof issue.code === "string" ? issue.code : undefined,
    detail: typeof issue.detail === "string" ? issue.detail : undefined,
  }));
}

function readErrorMessage(error: unknown): string {
  if (error instanceof LocalApiError && isRecord(error.body)) {
    if (typeof error.body.message === "string") return error.body.message;
    if (error.body.error === "validation") return "Import contains validation issues.";
  }
  if (error instanceof Error && error.message) return error.message;
  return "The local operation failed. Check the API and database, then try again.";
}

export function LocalDataWorkspace({ api, onSnapshotRefresh }: LocalDataWorkspaceProps) {
  const client = useMemo(() => api ?? createLocalApi(), [api]);
  const [connectionState, setConnectionState] = useState<ConnectionState>("checking");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [schema, setSchema] = useState<LocalSchemaResponse | null>(null);
  const [selectedTable, setSelectedTable] = useState("");
  const [jsonText, setJsonText] = useState("[]");
  const [operation, setOperation] = useState<"idle" | "seeding" | "importing" | "refreshing">("idle");
  const [operationMessage, setOperationMessage] = useState<string | null>(null);
  const [operationError, setOperationError] = useState<string | null>(null);
  const [issues, setIssues] = useState<ImportIssueView[]>([]);

  const checkConnection = useCallback(async (signal?: AbortSignal) => {
    setConnectionState("checking");
    setOperationError(null);
    try {
      const status = await client.getStatus(signal);
      if (status.database !== "connected") {
        setConnectionState("unavailable");
        setStatusMessage("Start the local API and PostgreSQL to use data tools.");
        return;
      }
      const nextSchema = await client.getSchema(signal);
      setSchema(nextSchema);
      setSelectedTable((current) => current || nextSchema.tables[0]?.table_name || "");
      setConnectionState("connected");
      setStatusMessage(status.schema === "ready"
        ? "Connected to the local PostgreSQL workspace."
        : "Database connected; run migrations or seed demo data to prepare the schema.");
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setConnectionState("unavailable");
      setStatusMessage("Start the local API and PostgreSQL to use data tools.");
    }
  }, [client]);

  useEffect(() => {
    const controller = new AbortController();
    void checkConnection(controller.signal);
    return () => controller.abort();
  }, [checkConnection]);

  const selectedSchema = schema?.tables.find((table) => table.table_name === selectedTable) ?? null;

  const clearOperationState = () => {
    setOperationMessage(null);
    setOperationError(null);
    setIssues([]);
  };

  const handleTableChange = (tableName: string) => {
    setSelectedTable(tableName);
    const nextTable = schema?.tables.find((table) => table.table_name === tableName);
    if (nextTable) {
      setJsonText(JSON.stringify(exampleForTable(nextTable), null, 2));
    }
    clearOperationState();
  };

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setJsonText(await file.text());
    clearOperationState();
  };

  const handleSeed = async () => {
    clearOperationState();
    setOperation("seeding");
    try {
      const result = await client.seed();
      const total = Object.values(result.row_counts).reduce((sum, count) => sum + count, 0);
      setOperationMessage(`Seeded demo data: ${formatCount(total, "record")}.`);
      await checkConnection();
    } catch (error: unknown) {
      setOperationError(readErrorMessage(error));
    } finally {
      setOperation("idle");
    }
  };

  const handleImport = async () => {
    clearOperationState();
    if (!selectedTable) {
      setOperationError("Choose a table before importing records.");
      return;
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(jsonText) as unknown;
    } catch {
      setOperationError("JSON is not valid. Paste an array of records or an object with a records array.");
      return;
    }
    const rawRecords = Array.isArray(parsed)
      ? parsed
      : isRecord(parsed) && Array.isArray(parsed.records)
        ? parsed.records
        : null;
    if (!rawRecords || !rawRecords.every(isRecord)) {
      setOperationError("JSON must contain an array of record objects.");
      return;
    }
    const payload: ImportPayload = { table: selectedTable, records: rawRecords };
    setOperation("importing");
    try {
      const result = await client.importRecords(payload);
      setOperationMessage(
        `Imported ${formatCount(result.received_count, "record")}: `
        + `${result.inserted_count} inserted, ${result.updated_count} updated.`,
      );
    } catch (error: unknown) {
      setOperationError(readErrorMessage(error));
      setIssues(readIssues(error));
    } finally {
      setOperation("idle");
    }
  };

  const handleRefresh = async () => {
    clearOperationState();
    setOperation("refreshing");
    try {
      await client.refresh();
      setOperationMessage("Snapshot refreshed. Reloading published data.");
      if (onSnapshotRefresh) onSnapshotRefresh();
      else window.location.reload();
    } catch (error: unknown) {
      setOperationError(readErrorMessage(error));
    } finally {
      setOperation("idle");
    }
  };

  return (
    <section className="local-workspace" aria-labelledby="local-workspace-title">
      <header className="local-workspace-header">
        <p className="section-kicker">Local data workspace</p>
        <h2 id="local-workspace-title">Connect local operational data</h2>
        <p>Use the local PostgreSQL pipeline to seed demo rows or import validated JSON records. The public snapshot remains read-only.</p>
      </header>

      {connectionState === "checking" && (
        <p className="local-workspace-status" role="status">Checking local connection</p>
      )}

      {connectionState === "unavailable" && (
        <div className="local-workspace-error" role="alert">
          <h3>Local API unavailable</h3>
          <p>{statusMessage ?? "Start the local API and PostgreSQL to use data tools."}</p>
          <p>Run <code>./.venv/Scripts/python.exe scripts/run_local_api.py</code> from the repository root.</p>
        </div>
      )}

      {connectionState === "connected" && schema && (
        <>
          <div className="local-workspace-status" role="status">
            <strong>Local database connected</strong>
            <span>{statusMessage}</span>
          </div>

          <div className="local-workspace-actions">
            <button type="button" onClick={handleSeed} disabled={operation !== "idle"}>
              Seed demo data
            </button>
            <button type="button" onClick={handleRefresh} disabled={operation !== "idle"}>
              Refresh snapshot
            </button>
          </div>

          <div className="local-workspace-editor">
            <div>
              <label htmlFor="local-import-table">Import table</label>
              <select
                id="local-import-table"
                aria-label="Import table"
                value={selectedTable}
                onChange={(event) => handleTableChange(event.target.value)}
              >
                {schema.tables.map((table) => (
                  <option key={table.table_name} value={table.table_name}>{table.table_name}</option>
                ))}
              </select>
              {selectedSchema && (
                <div className="local-workspace-guidance">
                  <p><strong>Primary key:</strong> {selectedSchema.primary_key}</p>
                  <p><strong>Fields:</strong> {selectedSchema.columns.map((column) => column.name).join(", ")}</p>
                  <details>
                    <summary>Example JSON</summary>
                    <pre>{JSON.stringify(exampleForTable(selectedSchema), null, 2)}</pre>
                  </details>
                </div>
              )}
            </div>

            <div>
              <label htmlFor="local-json-records">JSON records</label>
              <textarea
                id="local-json-records"
                aria-label="JSON records"
                value={jsonText}
                onChange={(event) => setJsonText(event.target.value)}
                rows={14}
                spellCheck={false}
              />
              <label className="local-workspace-file-label" htmlFor="local-json-file">Load JSON file</label>
              <input
                id="local-json-file"
                aria-label="Import JSON file"
                type="file"
                accept=".json,application/json"
                onChange={handleFileChange}
              />
              <button type="button" onClick={handleImport} disabled={operation !== "idle"}>
                Validate and import
              </button>
            </div>
          </div>
        </>
      )}

      {operation !== "idle" && (
        <p className="local-workspace-status" role="status">
          {operation === "seeding" && "Seeding demo data"}
          {operation === "importing" && "Validating and importing records"}
          {operation === "refreshing" && "Refreshing the published snapshot"}
        </p>
      )}
      {operationMessage && <p className="local-workspace-success" role="status">{operationMessage}</p>}
      {operationError && issues.length === 0 && (
        <p className="local-workspace-error" role="alert">{operationError}</p>
      )}
      {issues.length > 0 && (
        <div className="local-workspace-error" role="alert">
          <h3>Import validation issues</h3>
          {operationError && <p>{operationError}</p>}
          <ul>
            {issues.map((issue, index) => (
              <li key={`${issue.row_index}-${issue.field ?? "record"}-${index}`}>
                Row {issue.row_index + 1}{issue.field ? `, ${issue.field}` : ""}: {issue.detail ?? issue.code ?? "invalid record"}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
