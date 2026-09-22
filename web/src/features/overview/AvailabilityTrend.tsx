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
    ? `Hourly equipment availability ranged from ${(minimum * 100).toFixed(1)}% to ${(maximum * 100).toFixed(1)}%.`
    : "Hourly equipment availability is unavailable.";

  return (
    <div className="availability-trend">
      <div className="trend-plot">
        <div className="trend-axis" aria-hidden="true">
          <span>100%</span>
          <span>50%</span>
          <span>0%</span>
        </div>
        <div
          className="trend-chart"
          role="img"
          aria-label={`Hourly equipment availability chart on a 0% to 100% scale. ${summary}`}
        >
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
      </div>
      <p className="trend-summary">{summary}</p>
    </div>
  );
}
