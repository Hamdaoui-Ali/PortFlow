import { CircleCheck } from "lucide-react";

interface AvailabilityCardProps {
  value: number | null;
  generatedAt: string;
}

function formatTimestamp(value: string): { date: string; time: string } {
  const instant = new Date(value);
  return {
    date: new Intl.DateTimeFormat("en-GB", {
      day: "numeric",
      month: "long",
      timeZone: "UTC",
      year: "numeric",
    }).format(instant),
    time: new Intl.DateTimeFormat("en-GB", {
      hour: "2-digit",
      hour12: false,
      minute: "2-digit",
      timeZone: "UTC",
    }).format(instant),
  };
}

export function AvailabilityCard({ value, generatedAt }: AvailabilityCardProps) {
  const timestamp = formatTimestamp(generatedAt);
  const displayValue = value === null ? "Unavailable" : `${(value * 100).toFixed(1)}%`;

  return (
    <section className="availability-panel" aria-labelledby="availability-title">
      <div className="availability-icon" aria-hidden="true">
        <CircleCheck strokeWidth={1.75} />
      </div>
      <div>
        <h2 id="availability-title">Equipment availability</h2>
        <p className="availability-value">{displayValue}</p>
        <p className="availability-definition">
          Available intervals divided by scheduled intervals in the selected period.
        </p>
        <p className="availability-time">
          Updated <time dateTime={generatedAt}>{timestamp.date} &middot; {timestamp.time} UTC</time>
        </p>
      </div>
    </section>
  );
}
