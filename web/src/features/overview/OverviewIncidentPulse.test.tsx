import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { IncidentDatasetState } from "../../data/schema";
import { incidentRecords } from "../../test/incidentFixtures";
import { OverviewIncidentPulse } from "./OverviewIncidentPulse";

const records = incidentRecords.slice(0, 2);

describe("OverviewIncidentPulse", () => {
  it("renders ranked records with native incident links and visible context", () => {
    render(<OverviewIncidentPulse dataset={{ status: "ready", records }} />);

    expect(screen.getByRole("heading", { name: "Incident pulse" })).toBeInTheDocument();
    const pulse = screen.getByRole("list", { name: "Incident pulse records" });
    const links = screen.getAllByRole("link", { name: /^Open incident/ });

    expect(links.map((link) => link.getAttribute("href"))).toEqual([
      "?incident=inc-000002#incidents",
      "?incident=inc-000001#incidents",
    ]);
    expect(pulse).toHaveTextContent("CRITICAL");
    expect(pulse).toHaveTextContent("OPEN");
    expect(pulse).toHaveTextContent("Motor overload");
    expect(pulse).toHaveTextContent("TM-001 · QC-002");
  });

  it.each([
    [undefined, "Incident pulse is not included in this snapshot."],
    [{ status: "empty" }, "No incidents are present in this snapshot."],
    [{ status: "unavailable" }, "Incident pulse is unavailable for this snapshot."],
    [{ status: "malformed" }, "Incident pulse could not be read from this snapshot."],
    [{ status: "ready", records: [] }, "No incidents are present in this snapshot."],
  ] as const)("renders an honest dataset state", (dataset, message) => {
    render(<OverviewIncidentPulse dataset={dataset as IncidentDatasetState | undefined} />);

    expect(screen.getByRole("status")).toHaveTextContent(message);
    expect(screen.getByRole("status").tagName).toBe("OUTPUT");
    expect(screen.queryByRole("list", { name: "Incident pulse records" })).not.toBeInTheDocument();
  });
});
