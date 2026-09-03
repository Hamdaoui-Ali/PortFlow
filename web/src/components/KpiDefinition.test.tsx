import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { KpiDefinition } from "./KpiDefinition";

describe("KpiDefinition", () => {
  it("reveals the methodology through an accessible disclosure", () => {
    render(<KpiDefinition kpiId="throughput" />);

    const disclosure = screen.getByRole("group", { name: "About Throughput" });
    expect(disclosure).toBeInTheDocument();
    expect(screen.queryByText("Completed movement records")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("About"));

    expect(screen.getByText("Count of completed movement records.")).toBeInTheDocument();
    expect(screen.getByText("Formula")).toBeInTheDocument();
  });
});
