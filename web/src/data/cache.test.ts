import { describe, expect, it } from "vitest";

import type { SnapshotV1 } from "./schema";
import { SnapshotCache } from "./cache";

const snapshot = { snapshot_id: "demo-v2" } as unknown as SnapshotV1;

describe("SnapshotCache", () => {
  it("returns the last valid snapshot with its age", () => {
    const cache = new SnapshotCache();

    cache.set(snapshot, 1_000);

    expect(cache.get(4_500)).toEqual({ ageMs: 3_500, snapshot });
  });

  it("can be reset between sessions", () => {
    const cache = new SnapshotCache();
    cache.set(snapshot, 1_000);

    cache.clear();

    expect(cache.get(2_000)).toBeNull();
  });
});
