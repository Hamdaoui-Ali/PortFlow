import {
  Activity,
  AlertTriangle,
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  CircleGauge,
  Database,
  Grid2X2,
  HardHat,
  PlaySquare,
} from "lucide-react";
import { type ReactNode, useMemo, useState } from "react";

import { APP_NAME } from "./constants";

const navItems = [
  { label: "Overview", href: "#overview", icon: Grid2X2 },
  { label: "Equipment", href: "#equipment", icon: HardHat },
  { label: "Incidents", href: "#incidents", icon: AlertTriangle },
  { label: "Live Demo", href: "#live-demo", icon: PlaySquare },
  { label: "Data Health", href: "#data-health", icon: Activity },
] as const;

const terminalOptions = [
  { value: "all", label: "All terminals" },
  { value: "TM-001", label: "Casablanca Terminal" },
  { value: "TM-002", label: "Tangier Terminal" },
] as const;

const rangeOptions = [
  { value: "24h", label: "Last 24 hours" },
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
] as const;

interface AppShellProps {
  children: ReactNode;
}

function readFilter(name: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  return new URLSearchParams(window.location.search).get(name) ?? fallback;
}

export function AppShell({ children }: AppShellProps) {
  const [terminal, setTerminal] = useState(() => readFilter("terminal", "all"));
  const [range, setRange] = useState(() => readFilter("range", "24h"));

  const updateFilters = (nextTerminal: string, nextRange: string) => {
    const params = new URLSearchParams();
    if (nextTerminal !== "all") params.set("terminal", nextTerminal);
    if (nextRange !== "24h") params.set("range", nextRange);
    const query = params.toString();
    window.history.replaceState({}, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
  };

  const selectedTerminal = useMemo(
    () => terminalOptions.some((option) => option.value === terminal) ? terminal : "all",
    [terminal],
  );
  const selectedRange = useMemo(
    () => rangeOptions.some((option) => option.value === range) ? range : "24h",
    [range],
  );

  const handleTerminalChange = (value: string) => {
    setTerminal(value);
    updateFilters(value, selectedRange);
  };

  const handleRangeChange = (value: string) => {
    setRange(value);
    updateFilters(selectedTerminal, value);
  };

  return (
    <div className="app-frame">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <aside className="desktop-sidebar" aria-label="Sidebar">
        <a className="brand" href="#overview" aria-label={APP_NAME}>
          <img src={`${import.meta.env.BASE_URL}brand/portflow-mark.png`} alt="" />
          <span>{APP_NAME}</span>
        </a>
        <Navigation variant="desktop" />
        <div className="sidebar-footer">
          <Database size={16} aria-hidden="true" />
          <span>Static snapshot</span>
        </div>
      </aside>

      <div className="app-column">
        <header className="app-header">
          <div className="mobile-brand-row">
            <a className="brand" href="#overview" aria-label={APP_NAME}>
              <img src={`${import.meta.env.BASE_URL}brand/portflow-mark.png`} alt="" />
              <span>{APP_NAME}</span>
            </a>
            <span className="header-status"><CheckCircle2 size={15} aria-hidden="true" /> Healthy snapshot</span>
          </div>
          <div className="title-region">
            <div>
              <p className="eyebrow">Operations overview</p>
              <h1>Terminal Operations Control Tower</h1>
            </div>
            <p className="simulation-note">Simulated terminal operations data</p>
          </div>
          <div className="filter-band" aria-label="Global filters">
            <label className="filter-control">
              <span><CircleGauge size={16} aria-hidden="true" /> Terminal</span>
              <select value={selectedTerminal} onChange={(event) => handleTerminalChange(event.target.value)}>
                {terminalOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </label>
            <label className="filter-control">
              <span><CalendarDays size={16} aria-hidden="true" /> Date range</span>
              <select value={selectedRange} onChange={(event) => handleRangeChange(event.target.value)}>
                {rangeOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </label>
            <p className="filter-summary">Filters apply across operational views <ChevronRight size={15} aria-hidden="true" /></p>
          </div>
        </header>
        <main id="main-content" className="content" tabIndex={-1} aria-live="polite">
          {children}
        </main>
        <div className="mobile-navigation"><Navigation variant="mobile" /></div>
      </div>
    </div>
  );
}

function Navigation({ variant }: { variant: "desktop" | "mobile" }) {
  return (
    <nav className={`primary-navigation primary-navigation-${variant}`} aria-label="Primary navigation">
      {navItems.map(({ label, href, icon: Icon }, index) => (
        <a key={label} className={index === 0 ? "nav-link nav-link-active" : "nav-link"} href={href} aria-current={index === 0 ? "page" : undefined}>
          <Icon size={18} strokeWidth={1.8} aria-hidden="true" />
          <span>{label}</span>
        </a>
      ))}
    </nav>
  );
}
