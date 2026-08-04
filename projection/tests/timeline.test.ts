import { describe, expect, it } from "vitest";
import { linearProgress, loopPosition, noteVisualState } from "../src/playback/timeline";

describe("loopPosition", () => {
  it("normalizes positive and negative time", () => {
    expect(loopPosition(17_250, 16_000)).toBe(1_250);
    expect(loopPosition(-250, 16_000)).toBe(15_750);
  });
});

describe("noteVisualState", () => {
  it("is hidden before the approach window", () => {
    expect(noteVisualState(0, 2_000, 16_000)).toEqual({
      approachVisible: false,
      approachProgress: 0,
      hitVisible: false,
      hitProgress: 0
    });
  });

  it("derives approach and hit states from absolute time", () => {
    expect(noteVisualState(750, 1_000, 16_000).approachProgress).toBeCloseTo(5 / 6);
    expect(noteVisualState(1_000, 1_000, 16_000)).toMatchObject({
      approachVisible: true,
      approachProgress: 1,
      hitVisible: true,
      hitProgress: 0
    });
    expect(noteVisualState(1_210, 1_000, 16_000).hitProgress).toBeCloseTo(0.5);
  });

  it("shows an early note approach across the loop boundary", () => {
    const state = noteVisualState(15_500, 500, 16_000);
    expect(state.approachVisible).toBe(true);
    expect(state.approachProgress).toBeCloseTo(1 / 3);
  });
});

describe("linearProgress", () => {
  it("keeps visible radius travel until the hit and clamps its input", () => {
    expect(linearProgress(-1)).toBe(0);
    expect(linearProgress(0.5)).toBe(0.5);
    expect(linearProgress(0.8)).toBe(0.8);
    expect(linearProgress(2)).toBe(1);
  });
});
