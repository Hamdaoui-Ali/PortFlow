import { describe, expect, it } from "vitest";
import { readEquipmentUrlState, writeEquipmentUrlState } from "./equipmentUrlState";

describe("equipment URL state", () => {
  it("reads defaults when parameters are missing or invalid", () => {
    expect(readEquipmentUrlState("?sort=not-a-column&direction=sideways&equipment="))
      .toEqual({ direction: "asc", equipmentId: null, query: "", sort: "equipment_id" });
  });

  it("omits default values when writing URL state", () => {
    expect(writeEquipmentUrlState({
      direction: "asc",
      equipmentId: null,
      query: "",
      sort: "equipment_id",
    })).toBe("");
  });

  it("round-trips selected equipment, search, and sort state", () => {
    const state = {
      direction: "desc" as const,
      equipmentId: "QC-001",
      query: "qc 00",
      sort: "availability" as const,
    };
    expect(readEquipmentUrlState(writeEquipmentUrlState(state))).toEqual(state);
  });

  it("encodes URL values safely", () => {
    expect(writeEquipmentUrlState({
      direction: "asc",
      equipmentId: "QC/001",
      query: "QC 00+",
      sort: "terminal_id",
    })).toBe("search=QC+00%2B&sort=terminal_id&equipment=QC%2F001");
  });
});
