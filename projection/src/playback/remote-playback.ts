import type { PlaybackSnapshot } from "../network/protocol";

const INITIAL_SNAPSHOT: PlaybackSnapshot = {
  status: "stopped",
  scoreId: "demo-score",
  durationMs: 16_000,
  positionMs: 0,
  anchorPositionMs: 0,
  anchorClockMs: 0,
  speed: 1
};

export class RemotePlayback {
  #snapshot: PlaybackSnapshot = INITIAL_SNAPSHOT;

  apply(snapshot: PlaybackSnapshot): void {
    this.#snapshot = snapshot;
  }

  positionAt(serverTimeMs: number): number {
    const snapshot = this.#snapshot;
    if (snapshot.status !== "playing") return snapshot.positionMs;
    const elapsedMs = (serverTimeMs - snapshot.anchorClockMs) * snapshot.speed;
    return Math.min(snapshot.durationMs, Math.max(0, snapshot.anchorPositionMs + elapsedMs));
  }

  endingElapsedAt(serverTimeMs: number): number | undefined {
    const snapshot = this.#snapshot;
    if (snapshot.status !== "playing") return undefined;
    const remainingMs = Math.max(0, snapshot.durationMs - snapshot.anchorPositionMs);
    const endingStartedAtMs = snapshot.anchorClockMs + remainingMs / snapshot.speed;
    if (serverTimeMs < endingStartedAtMs) return undefined;
    return serverTimeMs - endingStartedAtMs;
  }

  get snapshot(): PlaybackSnapshot {
    return this.#snapshot;
  }
}
