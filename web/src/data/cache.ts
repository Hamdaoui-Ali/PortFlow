import type { SnapshotV1 } from "./schema";

interface CachedSnapshot {
  snapshot: SnapshotV1;
  storedAt: number;
}

export class SnapshotCache {
  private cached: CachedSnapshot | null = null;

  set(snapshot: SnapshotV1, storedAt = Date.now()): void {
    this.cached = { snapshot, storedAt };
  }

  get(now = Date.now()): { ageMs: number; snapshot: SnapshotV1 } | null {
    if (!this.cached) return null;
    return { ageMs: Math.max(0, now - this.cached.storedAt), snapshot: this.cached.snapshot };
  }

  clear(): void {
    this.cached = null;
  }
}

export const snapshotCache = new SnapshotCache();
