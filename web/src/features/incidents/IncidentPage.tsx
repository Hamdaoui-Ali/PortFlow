import { useEffect, useState } from "react";

import type { AppFilters } from "../../app/AppShell";
import type { IncidentDatasetState } from "../../data/schema";
import { IncidentDetail } from "./IncidentDetail";
import { IncidentTable } from "./IncidentTable";
import {
  filterIncidents,
  getIncidentMetrics,
  getIncidentTrend,
  getRootCauseCounts,
  sortIncidents,
  type IncidentSeverity,
  type IncidentSortColumn,
} from "./incidentData";
import { readIncidentUrlState, writeIncidentUrlState, type IncidentUrlState } from "./incidentUrlState";

interface IncidentPageProps {
  dataset: IncidentDatasetState;
  filters: AppFilters;
}

const incidentUrlKeys = ["search", "severity", "sort", "direction", "incident"] as const;

export function IncidentPage({ dataset, filters }: IncidentPageProps) {
  const [urlState, setUrlState] = useState(() => readIncidentUrlState(window.location.search));

  useEffect(() => {
    const restore = () => setUrlState(readIncidentUrlState(window.location.search));
    window.addEventListener("popstate", restore);
    return () => window.removeEventListener("popstate", restore);
  }, []);

  useEffect(() => {
    writeIncidentLocation(urlState, "replace");
  }, [filters.range, filters.terminal, urlState]);

  if (dataset.status !== "ready") return <IncidentDatasetMessage status={dataset.status} />;
  if (filters.range !== "24h") {
    return <div className="data-state data-state-warning" role="status"><h2>Incidents unavailable for selected filters</h2><p>The published incident snapshot covers the last 24 hours only.</p></div>;
  }

  const selectedRecord = urlState.incidentId ? dataset.records.find((record) => record.incident_id === urlState.incidentId) : undefined;
  const update = (next: IncidentUrlState, mode: "push" | "replace") => { writeIncidentLocation(next, mode); setUrlState(next); };
  const back = () => update({ ...urlState, incidentId: null }, "push");

  if (urlState.incidentId && !selectedRecord) {
    return <div className="data-state data-state-warning" role="status"><h2>Incident not found</h2><p>The selected incident is not present in this published snapshot.</p><button type="button" onClick={back}>Back to incident list</button></div>;
  }
  if (selectedRecord) return <IncidentDetail record={selectedRecord} onBack={back} />;

  const filtered = filterIncidents(dataset.records, urlState.query, filters.terminal, urlState.severity);
  const records = sortIncidents(filtered, urlState.sort, urlState.direction);
  const metrics = getIncidentMetrics(filtered);
  const trend = getIncidentTrend(filtered);
  const causes = getRootCauseCounts(filtered);
  const updateSort = (sort: IncidentSortColumn) => update({ ...urlState, sort, direction: urlState.sort === sort && urlState.direction === "asc" ? "desc" : "asc" }, "push");

  return (
    <section className="incident-page" aria-labelledby="incident-page-title">
      <header className="incident-page-header">
        <p className="section-kicker">Reliability analysis</p>
        <h2 id="incident-page-title">Incident exploration</h2>
        <p>Trace recurring faults from terminal patterns to one incident lifecycle.</p>
      </header>
      <section className="incident-metric-grid" aria-label="Incident summary">
        <Metric label="Incidents" value={String(metrics.totalCount)} />
        <Metric label="Open incidents" value={String(metrics.openCount)} />
        <Metric label="Average resolution" value={metrics.averageResolutionMinutes === null ? "—" : `${Math.round(metrics.averageResolutionMinutes)} min`} />
      </section>
      <section className="incident-analysis-grid" aria-label="Incident analysis">
        <AnalysisList title="Incident trend" items={trend.map((item) => ({ label: item.date, value: String(item.count) }))} empty="No trend data for these filters." />
        <AnalysisList title="Recurring root causes" items={causes.map((item) => ({ label: item.rootCause, value: String(item.count) }))} empty="No root causes for these filters." />
      </section>
      <IncidentTable
        records={records}
        query={urlState.query}
        severity={urlState.severity}
        sort={urlState.sort}
        direction={urlState.direction}
        onQueryChange={(query) => update({ ...urlState, query }, "replace")}
        onSeverityChange={(severity) => update({ ...urlState, severity }, "replace")}
        onSortChange={updateSort}
        onSelect={(incidentId) => update({ ...urlState, incidentId }, "push")}
      />
      {records.length === 0 ? <div className="data-state data-state-warning" role="status"><h3>No incidents match these filters</h3><p>Adjust the incident search, severity, or global terminal filter.</p></div> : null}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="incident-metric"><span>{label}</span><strong>{value}</strong></div>;
}

function AnalysisList({ title, items, empty }: { title: string; items: Array<{ label: string; value: string }>; empty: string }) {
  return <section className="analysis-card"><p className="section-kicker">Analysis</p><h3>{title}</h3>{items.length ? <ul>{items.map((item) => <li key={item.label}><span>{item.label}</span><strong>{item.value}</strong></li>)}</ul> : <p className="analysis-empty">{empty}</p>}</section>;
}

function IncidentDatasetMessage({ status }: { status: Exclude<IncidentDatasetState["status"], "ready"> }) {
  if (status === "absent") return <div className="data-state data-state-warning" role="status"><h2>Incident dataset not published</h2><p>This snapshot does not include incident history.</p></div>;
  if (status === "empty") return <div className="data-state" role="status"><h2>Incident history empty</h2><p>The published incident dataset contains no records.</p></div>;
  if (status === "malformed") return <div className="data-state data-state-error" role="alert"><h2>Published incident data malformed</h2><p>PortFlow could not validate the published incident data format.</p></div>;
  return <div className="data-state data-state-error" role="alert"><h2>Incident data unavailable</h2><p>PortFlow could not reach the published incident data.</p></div>;
}

function writeIncidentLocation(state: IncidentUrlState, mode: "push" | "replace") {
  const params = new URLSearchParams(window.location.search);
  for (const key of incidentUrlKeys) params.delete(key);
  const next = new URLSearchParams(writeIncidentUrlState(state));
  next.forEach((value, key) => params.set(key, value));
  const query = params.toString();
  const location = `${window.location.pathname}${query ? `?${query}` : ""}#incidents`;
  const current = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  if (location === current) return;
  if (mode === "push") window.history.pushState({}, "", location); else window.history.replaceState({}, "", location);
}
