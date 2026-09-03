import { describe, expect, it } from "vitest";

import { SnapshotLoadError, type SnapshotFailureKind } from "./errors";

describe("SnapshotLoadError", () => {
  it.each<[SnapshotFailureKind]>([["unavailable"], ["malformed"], ["empty"]])(
    "preserves the %s failure kind",
    (kind) => {
      const error = new SnapshotLoadError(kind);

      expect(error.kind).toBe(kind);
      expect(error.name).toBe("SnapshotLoadError");
    },
  );
});
