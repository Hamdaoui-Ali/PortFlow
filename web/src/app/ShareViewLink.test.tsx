import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ShareViewLink } from "./ShareViewLink";

describe("ShareViewLink", () => {
  it("copies the complete current view URL and announces success", async () => {
    const writeClipboard = vi.fn().mockResolvedValue(undefined);
    render(
      <ShareViewLink
        getUrl={() => "https://portflow.test/?terminal=TM-002&range=7d#equipment"}
        writeClipboard={writeClipboard}
      />,
    );

    expect(screen.getByRole("status")).not.toHaveAttribute("aria-live");
    fireEvent.click(screen.getByRole("button", { name: "Copy view link" }));

    await waitFor(() => expect(writeClipboard).toHaveBeenCalledWith(
      "https://portflow.test/?terminal=TM-002&range=7d#equipment",
    ));
    expect(screen.getByRole("status")).toHaveTextContent("View link copied.");
    expect(screen.getByRole("status")).toHaveAttribute("aria-live", "polite");
  });

  it("announces an actionable fallback when clipboard writing fails", async () => {
    const writeClipboard = vi.fn().mockRejectedValue(new Error("permission denied"));
    render(
      <ShareViewLink
        getUrl={() => "https://portflow.test/#incidents"}
        writeClipboard={writeClipboard}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Copy view link" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Copy unavailable. Use your browser address bar.",
    );
  });

  it("reads the URL at activation time", async () => {
    let currentUrl = "https://portflow.test/#overview";
    const writeClipboard = vi.fn().mockResolvedValue(undefined);
    render(<ShareViewLink getUrl={() => currentUrl} writeClipboard={writeClipboard} />);
    currentUrl = "https://portflow.test/?equipment=QC-001#equipment";

    fireEvent.click(screen.getByRole("button", { name: "Copy view link" }));

    await waitFor(() => expect(writeClipboard).toHaveBeenCalledWith(currentUrl));
  });
});
