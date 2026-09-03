import { describe, expect, it } from "vitest";

import { KPI_DEFINITIONS, KPI_IDS } from "./kpis";

describe("KPI catalog", () => {
  it("documents every Overview KPI with auditable methodology", () => {
    expect(Object.keys(KPI_DEFINITIONS)).toEqual(KPI_IDS);

    for (const definition of Object.values(KPI_DEFINITIONS)) {
      expect(definition.label).toBeTruthy();
      expect(definition.formula).toBeTruthy();
      expect(definition.grain).toBeTruthy();
      expect(definition.timeBoundary).toBeTruthy();
      expect(definition.exclusions).toBeTruthy();
      expect(definition.zeroDenominator).toBeTruthy();
    }
  });
});
