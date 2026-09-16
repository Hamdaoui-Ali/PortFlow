import type { ReplayEvent } from "./hourlyAvailability";
import { groupHourlyAvailability } from "./hourlyAvailability";

interface AvailabilityTrendProps {
  events: ReplayEvent[];
}

export function AvailabilityTrend({ events }: AvailabilityTrendProps) {
  const points = groupHourlyAvailability(events);
  const values = points.map((point) => point.value);
  const minimum = values.length ? Math.min(...values) : 0;
  const maximum = values.length ? Math.max(...values) : 0;
  const summary = values.length
    ? `Hourly availability ranged from ${(minimum * 100).toFixed(1)}% to ${(maximum * 100).toFixed(1)}%.`
    : "Hourly availability is unavailable.";

  return (
    <div className="availability-trend">
      <div className="trend-chart" role="img" aria-label={`Hourly availability trend. ${summary}`}>
        {points.map((point, pointIndex) => {
          const isCheckpoint = pointIndex % 4 === 0 || pointIndex === points.length - 1;

          return (
            <div className="trend-point" key={point.label}>
              <div className="trend-bar-track">
                <div className="trend-bar" style={{ height: `${Math.max(point.value * 100, 2)}%` }} />
              </div>
              <span className={isCheckpoint ? "trend-label-visible" : "trend-label-hidden"}>
                {point.label}
              </span>
            </div>
          );
        })}
      </div>
      <p className="trend-summary">{summary}</p>
    </div>
  );
}
