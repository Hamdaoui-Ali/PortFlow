import type { ReplayEventV1 } from "../../data/schema";
import { formatReplayEvent, formatReplayTimestamp } from "./replayPresentation";

export function ReplayActivityFeed({ events }: { events: ReplayEventV1[] }) {
  return (
    <section className="replay-activity-panel" aria-labelledby="replay-activity-title">
      <div>
        <p className="section-kicker">Event stream</p>
        <h2 id="replay-activity-title">Replay activity</h2>
      </div>
      <ul className="replay-activity-feed" aria-label="Replay activity">
        {events.map((event) => (
          <li key={event.event_id}>
            <strong>{formatReplayEvent(event)}</strong>
            <time dateTime={event.event_timestamp}>{formatReplayTimestamp(event.event_timestamp)}</time>
          </li>
        ))}
      </ul>
    </section>
  );
}
