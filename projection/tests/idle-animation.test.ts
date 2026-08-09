import { describe, expect, it } from "vitest";
import {
  IDLE_FADE_IN_MS,
  IDLE_CYCLE_MS,
  idleCometVisualState,
  idleCycleVariant,
  idlePadVisualState,
  idleRippleVisualStates,
  idleStrength,
} from "../src/scene/idle-animation";

describe("idle animation", () => {
  it("fades in without jumping away from the static layout", () => {
    expect(idleStrength(0)).toBe(0);
    expect(idlePadVisualState(0, 0)).toMatchObject({
      scale: 1,
      glowAlpha: 0,
      flowAlpha: 0,
      coreFlowAlpha: 0
    });
    expect(idleStrength(IDLE_FADE_IN_MS)).toBe(1);
  });

  it("keeps the center charge and emits three high-contrast ripples", () => {
    const centerCharge = idlePadVisualState(1_000, 0, 0, 0, true);
    const ripples = idleRippleVisualStates(2_300);

    expect(centerCharge.scale).toBeGreaterThan(1.04);
    expect(centerCharge.glowAlpha).toBeGreaterThan(0.5);
    expect(ripples).toHaveLength(3);
    expect(ripples.every((ripple) => ripple.alpha > 0.3)).toBe(true);
  });

  it("varies the chase once per cycle while remaining deterministic for a seed", () => {
    const seed = 20260809;
    const first = idleCycleVariant(4_000, seed);
    const repeatedRead = idleCycleVariant(4_000, seed);
    const variants = Array.from({ length: 8 }, (_, index) =>
      idleCycleVariant(index * IDLE_CYCLE_MS + 4_000, seed)
    );

    expect(repeatedRead).toEqual(first);
    expect(new Set(variants.map((variant) => variant.startPosition)).size).toBeGreaterThan(2);
    expect(new Set(variants.map((variant) => variant.direction)).size).toBe(2);
    expect(new Set(variants.map((variant) => variant.chaseDurationMs)).size).toBeGreaterThan(1);
    expect(variants.slice(1).every((variant, index) =>
      JSON.stringify(variant) !== JSON.stringify(variants[index])
    )).toBe(true);
  });

  it("shows bright comet trails that follow the randomized chase", () => {
    const comets = Array.from({ length: 8 }, (_, index) =>
      idleCometVisualState(4_200, index, 20260809)
    );
    const brightest = comets.reduce((best, comet) =>
      comet.alpha > best.alpha ? comet : best
    );

    expect(brightest.alpha).toBeGreaterThan(0.75);
    expect(brightest.scale).toBeGreaterThan(1.2);
    expect(brightest.x).toBeGreaterThan(0);
    expect(brightest.x).toBeLessThan(1);
  });
});
