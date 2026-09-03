import { describe, expect, it } from "vitest";

import { readIncidentUrlState, writeIncidentUrlState } from "./incidentUrlState";

describe("incident URL state", () => {
  it("reads safe defaults for invalid parameters", () => {
    expect(readIncidentUrlState("?severity=urgent&direction=sideways&incident="))
      .toEqual({ direction: "desc", incidentId: null, query: "", severity: "all", sort: "opened_at" });
  });

  it("round-trips incident filters, sorting, and selected detail", () => {
    const state = {
      direction: "asc" as const,
      incidentId: "inc-000002",
      query: "motor",
      severity: "CRITICAL" as const,
      sort: "severity" as const,
    };
    expect(readIncidentUrlState(writeIncidentUrlState(state))).toEqual(state);
  });
});
