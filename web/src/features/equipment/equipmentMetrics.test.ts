import { describe, expect, it } from "vitest";

import { formatMetric, formatMinutes, formatPercentage } from "./equipmentMetrics";

describe("equipment metric formatting", () => {
  it("formats percentages and unavailable values consistently", () => {
    expect(formatPercentage(0.9444444444444444)).toBe("94.4%");
    expect(formatPercentage(null)).toBe("Unavailable");
    expect(formatPercentage(undefined)).toBe("Unavailable");
  });

  it("formats integer and fractional metrics with their units", () => {
    expect(formatMinutes(80)).toBe("80 min");
    expect(formatMinutes(30.25)).toBe("30.3 min");
    expect(formatMetric(24, "hr")).toBe("24 hr");
    expect(formatMetric(null, "hr")).toBe("Unavailable");
  });
});
