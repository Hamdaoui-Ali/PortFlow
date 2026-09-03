import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { OverviewV1, ReplayEventV1 } from "../../data/schema";
import { LiveDemoPage } from "./LiveDemoPage";

const overview: OverviewV1 = {
  active_incidents: 1,
  active_intervals: 202,
  availability: { available_intervals: 272, scheduled_intervals: 288, value: 0.9444444444 },
  available_intervals: 272,
  average_dwell_minutes: 63.75,
  critical_alarms: 1,
  mtbf_hours: 24,
  mttr_minutes: 30,
  operating_hours: 24,
  qualifying_failure_count: 1,
  repair_minutes: 30,
  resolved_incident_count: 1,
  scheduled_intervals: 288,
  schema_version: 1,
  source_period_end: "2026-09-02T23:55:00Z",
  source_period_start: "2026-09-02T00:00:00Z",
  terminal_id: "TM-001",
  throughput: 4,
  utilization: 0.7426,
};

const events: ReplayEventV1[] = [
  {
    available: true,
    equipment_id: "QC-001",
    event_id: "evt-1",
    event_timestamp: "2026-09-02T00:00:00Z",
    state: "ACTIVE",
    terminal_id: "TM-001",
  },
  {
    available: false,
    equipment_id: "QC-001",
    event_id: "evt-2",
    event_timestamp: "2026-09-02T00:00:05Z",
    state: "WARNING",
    terminal_id: "TM-001",
  },
  {
    available: true,
    equipment_id: "QC-001",
    event_id: "evt-3",
    event_timestamp: "2026-09-02T00:00:10Z",
    state: "ACTIVE",
    terminal_id: "TM-001",
  },
];

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("LiveDemoPage", () => {
  it("renders the disclosure, heading, controls, and initial status", () => {
    render(<LiveDemoPage events={events} overview={overview} />);

    expect(screen.getByRole("heading", { name: "Live Demo" })).toBeInTheDocument();
    expect(screen.getByText("Simulation — not live operational data")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start replay" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reset replay" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Replay speed" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Replay idle");
  });

  it("starts replay and applies an event on each timer tick", () => {
    vi.useFakeTimers();
    render(<LiveDemoPage events={events} overview={overview} />);

    fireEvent.click(screen.getByRole("button", { name: "Start replay" }));
    expect(screen.getByRole("status")).toHaveTextContent("Replay playing");
    expect(screen.getByRole("list", { name: "Replay activity" })).toHaveTextContent("evt-1");

    act(() => vi.advanceTimersByTime(5_000));
    expect(screen.getByRole("list", { name: "Replay activity" })).toHaveTextContent("evt-2");
    expect(screen.getByText("2 of 3 events")).toBeInTheDocument();
  });

  it("pauses, resumes, resets, and changes speed with native controls", () => {
    vi.useFakeTimers();
    render(<LiveDemoPage events={events} overview={overview} />);

    fireEvent.click(screen.getByRole("button", { name: "Start replay" }));
    fireEvent.click(screen.getByRole("button", { name: "Pause replay" }));
    expect(screen.getByRole("status")).toHaveTextContent("Replay paused");
    fireEvent.change(screen.getByRole("combobox", { name: "Replay speed" }), { target: { value: "4" } });
    expect(screen.getByRole("combobox", { name: "Replay speed" })).toHaveValue("4");
    fireEvent.click(screen.getByRole("button", { name: "Resume replay" }));
    expect(screen.getByRole("status")).toHaveTextContent("Replay playing");
    fireEvent.click(screen.getByRole("button", { name: "Reset replay" }));
    expect(screen.getByRole("status")).toHaveTextContent("Replay idle");
    expect(screen.getByText("0 of 3 events")).toBeInTheDocument();
  });

  it("renders honest empty and unpublished states without starting a timer", () => {
    vi.useFakeTimers();
    const { rerender } = render(<LiveDemoPage events={[]} overview={overview} />);
    expect(screen.getByRole("status")).toHaveTextContent("Replay has no events");
    expect(screen.queryByRole("button", { name: "Start replay" })).not.toBeInTheDocument();

    rerender(<LiveDemoPage overview={overview} />);
    expect(screen.getByRole("status")).toHaveTextContent("Replay dataset not published");
    expect(vi.getTimerCount()).toBe(0);
  });

  it("keeps reduced-motion replay logic identical", () => {
    vi.useFakeTimers();
    vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: true })));
    render(<LiveDemoPage events={events} overview={overview} />);

    fireEvent.click(screen.getByRole("button", { name: "Start replay" }));
    act(() => vi.advanceTimersByTime(5_000));
    expect(screen.getByText("2 of 3 events")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Replay activity" })).toHaveTextContent("evt-2");
  });

  it("completes once and stops timer work after the final event", () => {
    vi.useFakeTimers();
    render(<LiveDemoPage events={events} overview={overview} />);

    fireEvent.change(screen.getByRole("combobox", { name: "Replay speed" }), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "Start replay" }));
    act(() => vi.advanceTimersByTime(5_000));
    act(() => vi.advanceTimersByTime(5_000));

    expect(screen.getByRole("status")).toHaveTextContent("Replay complete");
    expect(screen.getByText("3 of 3 events")).toBeInTheDocument();
    expect(vi.getTimerCount()).toBe(0);
    fireEvent.click(screen.getByRole("button", { name: "Reset replay" }));
    expect(screen.getByRole("combobox", { name: "Replay speed" })).toHaveValue("2");
  });
});
