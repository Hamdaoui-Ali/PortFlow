import { fireEvent, screen, waitFor } from "@testing-library/react";
import { expect, it } from "vitest";

interface FilterRecoveryTestConfig {
  readonly resource: "Equipment" | "Incidents";
  readonly readyHeading: string;
  readonly tableName: string;
  readonly renderPage: () => void;
}

export function defineFilterRecoveryTests({
  resource,
  readyHeading,
  tableName,
  renderPage,
}: FilterRecoveryTestConfig): void {
  const recoveryHeading = `${resource} unavailable for selected filters`;

  it(`shows ${resource.toLowerCase()} recovery for an unsupported terminal`, async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: readyHeading })).toBeInTheDocument();

    fireEvent.change(screen.getByRole("combobox", { name: "Terminal" }), {
      target: { value: "TM-002" },
    });

    expect(await screen.findByRole("heading", { name: recoveryHeading })).toBeInTheDocument();
    expect(screen.getByText(/Published scope:/)).toHaveTextContent("Casablanca Terminal");
    expect(screen.queryByRole("table", { name: tableName })).not.toBeInTheDocument();
  });

  it(`resets ${resource.toLowerCase()} recovery for an unsupported range`, async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: readyHeading })).toBeInTheDocument();

    fireEvent.change(screen.getByRole("combobox", { name: "Date range" }), {
      target: { value: "7d" },
    });

    expect(await screen.findByRole("heading", { name: recoveryHeading })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reset filters to published scope" }));

    expect(window.location.search).toBe("");
    expect(await screen.findByRole("heading", { name: readyHeading })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("main")).toHaveFocus());
  });
}
