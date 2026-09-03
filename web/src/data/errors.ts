export type SnapshotFailureKind = "unavailable" | "malformed" | "empty";

export class SnapshotLoadError extends Error {
  readonly kind: SnapshotFailureKind;

  constructor(kind: SnapshotFailureKind, message = `Snapshot ${kind}`) {
    super(message);
    this.name = "SnapshotLoadError";
    this.kind = kind;
  }
}
