export const APPROACH_LEAD_MS = 1_500;
export const HIT_DURATION_MS = 420;

export interface NoteVisualState {
  readonly approachVisible: boolean;
  readonly approachProgress: number;
  readonly hitVisible: boolean;
  readonly hitProgress: number;
}

export function loopPosition(elapsedMs: number, durationMs: number): number {
  if (durationMs <= 0) throw new RangeError("durationMs must be positive");
  return ((elapsedMs % durationMs) + durationMs) % durationMs;
}

export function noteVisualState(
  playbackTimeMs: number,
  noteTimeMs: number,
  durationMs: number,
  approachLeadMs = APPROACH_LEAD_MS,
  hitDurationMs = HIT_DURATION_MS
): NoteVisualState {
  const positionMs = loopPosition(playbackTimeMs, durationMs);
  const untilHitMs = loopPosition(noteTimeMs - positionMs, durationMs);
  const sinceHitMs = loopPosition(positionMs - noteTimeMs, durationMs);
  const approachVisible = untilHitMs <= approachLeadMs;
  const hitVisible = sinceHitMs < hitDurationMs;

  return {
    approachVisible,
    approachProgress: approachVisible ? 1 - untilHitMs / approachLeadMs : 0,
    hitVisible,
    hitProgress: hitVisible ? sinceHitMs / hitDurationMs : 0
  };
}

export function linearProgress(value: number): number {
  const clamped = Math.min(1, Math.max(0, value));
  return clamped;
}
