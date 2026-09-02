import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "./App";

describe("App", () => {
  it("identifies the control tower and simulated data source", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: "Terminal Operations Control Tower" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Simulated terminal operations data")).toBeInTheDocument();
  });
});
