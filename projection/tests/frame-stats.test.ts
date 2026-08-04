import { describe, expect, it } from "vitest";
import { FrameStats } from "../src/debug/frame-stats";

describe("FrameStats", () => {
  it("calculates frame duration and sampled FPS from an explicit clock", () => {
    const stats = new FrameStats(100);
    expect(stats.update(0)).toEqual({ fps: 0, frameTimeMs: 0 });
    expect(stats.update(50)).toEqual({ fps: 0, frameTimeMs: 50 });
    expect(stats.update(100)).toEqual({ fps: 30, frameTimeMs: 50 });
  });

  it("rejects an invalid sample window", () => {
    expect(() => new FrameStats(0)).toThrow(RangeError);
  });
});

