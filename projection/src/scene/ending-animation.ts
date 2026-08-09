export const ENDING_ANIMATION_DURATION_MS = 6_000;
export type EndingAnimationStyle = "calm" | "spectacular";

export interface EndingVisualState {
  readonly elapsedMs: number;
  readonly style: EndingAnimationStyle;
  readonly complete: boolean;
  readonly lastGlow: number;
  readonly rippleProgress: number;
  readonly rippleAlpha: number;
  readonly resonance: number;
  readonly gathering: number;
  readonly haloProgress: number;
  readonly haloAlpha: number;
  readonly burst: number;
  readonly flash: number;
  readonly drumAlpha: number;
}

export function endingVisualState(
  elapsedMs: number,
  style: EndingAnimationStyle = "calm"
): EndingVisualState {
  const elapsed = Math.max(0, elapsedMs);
  const spectacular = style === "spectacular";
  const rippleProgress = smoothstep(segment(elapsed, 0, spectacular ? 1_900 : 1_400));
  const resonanceProgress = segment(
    elapsed,
    spectacular ? 350 : 650,
    spectacular ? 3_050 : 2_700
  );
  const haloProgress = smoothstep(segment(
    elapsed,
    spectacular ? 2_250 : 2_700,
    spectacular ? 4_300 : 4_450
  ));

  let drumAlpha = 1;
  const fadeOutStart = spectacular ? 4_050 : 3_650;
  const blackStart = spectacular ? 4_550 : 4_400;
  if (elapsed >= fadeOutStart && elapsed < blackStart) {
    drumAlpha = 1 - smoothstep(segment(elapsed, fadeOutStart, blackStart));
  } else if (elapsed >= blackStart && elapsed < 4_800) {
    drumAlpha = 0;
  } else if (elapsed >= 4_800) {
    drumAlpha = smoothstep(segment(elapsed, 4_800, ENDING_ANIMATION_DURATION_MS));
  }

  return {
    elapsedMs: elapsed,
    style,
    complete: elapsed >= ENDING_ANIMATION_DURATION_MS,
    lastGlow: 1 - smoothstep(segment(elapsed, 0, spectacular ? 1_450 : 1_200)),
    rippleProgress,
    rippleAlpha: (1 - rippleProgress) * (spectacular ? 0.95 : 0.72),
    resonance: Math.sin(Math.PI * resonanceProgress),
    gathering: smoothstep(segment(
      elapsed,
      spectacular ? 900 : 1_450,
      spectacular ? 3_400 : 3_750
    )),
    haloProgress,
    haloAlpha: Math.sin(Math.PI * haloProgress) * (spectacular ? 0.72 : 0.42),
    burst: Math.sin(Math.PI * segment(elapsed, 3_150, 4_250)) * (spectacular ? 1 : 0),
    flash: Math.sin(Math.PI * segment(elapsed, 3_250, 3_700)) * (spectacular ? 1 : 0),
    drumAlpha
  };
}

export function segment(value: number, start: number, end: number): number {
  return Math.min(1, Math.max(0, (value - start) / (end - start)));
}

function smoothstep(value: number): number {
  return value * value * (3 - 2 * value);
}
