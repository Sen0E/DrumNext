export const ENDING_ANIMATION_DURATION_MS = 6_000;

export interface EndingVisualState {
  readonly elapsedMs: number;
  readonly complete: boolean;
  readonly lastGlow: number;
  readonly rippleProgress: number;
  readonly rippleAlpha: number;
  readonly resonance: number;
  readonly gathering: number;
  readonly haloProgress: number;
  readonly haloAlpha: number;
  readonly drumAlpha: number;
}

export function endingVisualState(elapsedMs: number): EndingVisualState {
  const elapsed = Math.max(0, elapsedMs);
  const rippleProgress = smoothstep(segment(elapsed, 0, 1_400));
  const resonanceProgress = segment(elapsed, 650, 2_700);
  const haloProgress = smoothstep(segment(elapsed, 2_700, 4_450));

  let drumAlpha = 1;
  if (elapsed >= 3_650 && elapsed < 4_400) {
    drumAlpha = 1 - smoothstep(segment(elapsed, 3_650, 4_400));
  } else if (elapsed >= 4_400 && elapsed < 4_800) {
    drumAlpha = 0;
  } else if (elapsed >= 4_800) {
    drumAlpha = smoothstep(segment(elapsed, 4_800, ENDING_ANIMATION_DURATION_MS));
  }

  return {
    elapsedMs: elapsed,
    complete: elapsed >= ENDING_ANIMATION_DURATION_MS,
    lastGlow: 1 - smoothstep(segment(elapsed, 0, 1_200)),
    rippleProgress,
    rippleAlpha: (1 - rippleProgress) * 0.72,
    resonance: Math.sin(Math.PI * resonanceProgress),
    gathering: smoothstep(segment(elapsed, 1_450, 3_750)),
    haloProgress,
    haloAlpha: Math.sin(Math.PI * haloProgress) * 0.42,
    drumAlpha
  };
}

export function segment(value: number, start: number, end: number): number {
  return Math.min(1, Math.max(0, (value - start) / (end - start)));
}

function smoothstep(value: number): number {
  return value * value * (3 - 2 * value);
}
