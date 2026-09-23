import type { ReactNode } from "react";

type NonReadyPulseStatus = "absent" | "empty" | "unavailable" | "malformed";

const pulseMessageSuffix = {
  absent: "is not included in",
  unavailable: "is unavailable for",
  malformed: "could not be read from",
} as const;

interface ReadyPulse<T> {
  readonly status: "ready";
  readonly records: readonly T[];
}

interface OverviewPulseSectionProps<T> {
  readonly pulse: ReadyPulse<T> | { readonly status: NonReadyPulseStatus };
  readonly eyebrow: string;
  readonly title: string;
  readonly titleId: string;
  readonly description: string;
  readonly renderRecord: (record: T) => ReactNode;
}

export function OverviewPulseSection<T>({
  pulse,
  eyebrow,
  title,
  titleId,
  description,
  renderRecord,
}: OverviewPulseSectionProps<T>) {
  const resourceName = title.slice(0, title.indexOf(" "));
  const content = pulse.status === "ready"
    ? <ul className="equipment-incident-list" aria-label={`${title} records`}>{pulse.records.map(renderRecord)}</ul>
    : <output className="equipment-context-message">{pulseMessage(resourceName, pulse.status)}</output>;

  return (
    <section className="equipment-context" aria-labelledby={titleId}>
      <div className="equipment-context-header">
        <p className="section-kicker">{eyebrow}</p>
        <h2 id={titleId}>{title}</h2>
        <p>{description}</p>
      </div>
      {content}
    </section>
  );
}

function pulseMessage(resourceName: string, status: NonReadyPulseStatus): string {
  if (status === "absent") return `${resourceName} pulse is not included in this snapshot.`;
  if (status === "empty") {
    return resourceName[0] === "I"
      ? "No incidents are present in this snapshot."
      : "No equipment records are present in this snapshot.";
  }
  return `${resourceName} pulse ${pulseMessageSuffix[status]} this snapshot.`;
}
