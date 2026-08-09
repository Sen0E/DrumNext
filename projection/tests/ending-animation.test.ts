import { describe, expect, it } from "vitest";
import {
  ENDING_ANIMATION_DURATION_MS,
  endingVisualState
} from "../src/scene/ending-animation";

describe("endingVisualState", () => {
  it("moves from the final glow into ripple and gathering phases", () => {
    const start = endingVisualState(0);
    const gathering = endingVisualState(2_500);

    expect(start.lastGlow).toBe(1);
    expect(start.rippleProgress).toBe(0);
    expect(gathering.gathering).toBeGreaterThan(0);
    expect(gathering.rippleAlpha).toBe(0);
  });

  it("fades to black before restoring the static drums", () => {
    expect(endingVisualState(4_600).drumAlpha).toBe(0);
    expect(endingVisualState(5_400).drumAlpha).toBeGreaterThan(0);
    expect(endingVisualState(ENDING_ANIMATION_DURATION_MS)).toMatchObject({
      complete: true,
      drumAlpha: 1
    });
  });

  it("adds a brighter burst phase for the spectacular style", () => {
    const calm = endingVisualState(3_450, "calm");
    const spectacular = endingVisualState(3_450, "spectacular");

    expect(calm.burst).toBe(0);
    expect(spectacular.burst).toBeGreaterThan(0);
    expect(spectacular.flash).toBeGreaterThan(0);
    expect(spectacular.haloAlpha).toBeGreaterThan(calm.haloAlpha);
  });
});
