import { useEffect, useState } from "react";

import type { AppFilters } from "../../app/AppShell";
import type { EquipmentDatasetState } from "../../data/schema";
import { EquipmentDetail } from "./EquipmentDetail";
import { EquipmentTable } from "./EquipmentTable";
import { filterEquipment, type EquipmentSortColumn } from "./equipmentTableData";
import {
  readEquipmentUrlState,
  writeEquipmentUrlState,
  type EquipmentUrlState,
} from "./equipmentUrlState";

interface EquipmentPageProps {
  dataset: EquipmentDatasetState;
  filters: AppFilters;
}

const equipmentUrlKeys = ["search", "sort", "direction", "equipment"] as const;

export function EquipmentPage({ dataset, filters }: EquipmentPageProps) {
  const [urlState, setUrlState] = useState(() => readEquipmentUrlState(window.location.search));

  useEffect(() => {
    const restoreUrlState = () => setUrlState(readEquipmentUrlState(window.location.search));
    window.addEventListener("popstate", restoreUrlState);
    return () => window.removeEventListener("popstate", restoreUrlState);
  }, []);

  useEffect(() => {
    writeEquipmentLocation(urlState, "replace");
  }, [filters.range, filters.terminal, urlState]);

  const updateUrlState = (nextState: EquipmentUrlState, mode: "push" | "replace") => {
    writeEquipmentLocation(nextState, mode);
    setUrlState(nextState);
  };

  if (dataset.status !== "ready") {
    return <EquipmentDatasetMessage status={dataset.status} />;
  }

  if (filters.range !== "24h") {
    return (
      <div className="data-state data-state-warning" role="status">
        <h2>Equipment unavailable for selected filters</h2>
        <p>The published equipment snapshot covers the last 24 hours only.</p>
      </div>
    );
  }

  const selectedRecord = urlState.equipmentId
    ? dataset.records.find((record) => record.equipment_id === urlState.equipmentId)
    : undefined;

  const returnToFleet = () => updateUrlState({ ...urlState, equipmentId: null }, "push");

  if (urlState.equipmentId && !selectedRecord) {
    return (
      <div className="data-state data-state-warning" role="status">
        <h2>Equipment not found</h2>
        <p>The selected equipment ID is not present in this published snapshot.</p>
        <button type="button" onClick={returnToFleet}>Back to equipment fleet</button>
      </div>
    );
  }

  if (selectedRecord) {
    return <EquipmentDetail record={selectedRecord} onBack={returnToFleet} />;
  }

  const visibleRecords = filterEquipment(dataset.records, urlState.query, filters.terminal);

  const handleSortChange = (column: EquipmentSortColumn) => {
    const direction = urlState.sort === column && urlState.direction === "asc" ? "desc" : "asc";
    updateUrlState({ ...urlState, direction, sort: column }, "push");
  };

  return (
    <section className="equipment-page" aria-labelledby="equipment-page-title">
      <header className="equipment-page-header">
        <p className="section-kicker">Fleet operations</p>
        <h2 id="equipment-page-title">Equipment fleet</h2>
        <p>Search, sort, and inspect equipment in the published operational snapshot.</p>
      </header>
      <EquipmentTable
        records={dataset.records}
        query={urlState.query}
        terminal={filters.terminal}
        sort={urlState.sort}
        direction={urlState.direction}
        onQueryChange={(query) => updateUrlState({ ...urlState, query }, "replace")}
        onSortChange={handleSortChange}
        onSelect={(equipmentId) => updateUrlState({ ...urlState, equipmentId }, "push")}
      />
      {visibleRecords.length === 0 ? (
        <div className="data-state data-state-warning" role="status" aria-label="No matching equipment">
          <h3>No equipment matches these filters</h3>
          <p>Adjust the equipment search or global terminal filter.</p>
        </div>
      ) : null}
    </section>
  );
}

function EquipmentDatasetMessage({ status }: { status: Exclude<EquipmentDatasetState["status"], "ready"> }) {
  if (status === "absent") {
    return (
      <div className="data-state data-state-warning" role="status">
        <h2>Equipment dataset not published</h2>
        <p>This snapshot does not include an equipment dataset.</p>
      </div>
    );
  }
  if (status === "malformed") {
    return (
      <div className="data-state data-state-error" role="alert">
        <h2>Published equipment data malformed</h2>
        <p>PortFlow could not validate the published equipment data format.</p>
      </div>
    );
  }
  if (status === "empty") {
    return (
      <div className="data-state" role="status">
        <h2>Equipment fleet empty</h2>
        <p>The published equipment dataset contains no records.</p>
      </div>
    );
  }
  return (
    <div className="data-state data-state-error" role="alert">
      <h2>Equipment data unavailable</h2>
      <p>PortFlow could not reach the published equipment data.</p>
    </div>
  );
}

function writeEquipmentLocation(state: EquipmentUrlState, mode: "push" | "replace") {
  const params = new URLSearchParams(window.location.search);
  for (const key of equipmentUrlKeys) params.delete(key);

  const equipmentParams = new URLSearchParams(writeEquipmentUrlState(state));
  equipmentParams.forEach((value, key) => params.set(key, value));

  const query = params.toString();
  const nextLocation = `${window.location.pathname}${query ? `?${query}` : ""}#equipment`;
  const currentLocation = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  if (nextLocation === currentLocation) return;

  if (mode === "push") window.history.pushState({}, "", nextLocation);
  else window.history.replaceState({}, "", nextLocation);
}
