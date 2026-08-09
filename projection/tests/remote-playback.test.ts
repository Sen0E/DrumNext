import { describe, expect, it } from "vitest";
import { RemotePlayback } from "../src/playback/remote-playback";

describe("RemotePlayback", () => {
  it("derives a playing position from the server clock", () => {
    const playback = new RemotePlayback();
    playback.apply({
      status: "playing",
      scoreId: "demo-score",
      durationMs: 16_000,
      positionMs: 2_000,
      anchorPositionMs: 2_000,
      anchorClockMs: 10_000,
      speed: 1.5
    });
    expect(playback.positionAt(11_000)).toBe(3_500);
  });

  it("holds a paused position", () => {
    const playback = new RemotePlayback();
    playback.apply({
      status: "paused",
      scoreId: "demo-score",
      durationMs: 16_000,
      positionMs: 4_200,
      anchorPositionMs: 4_200,
      anchorClockMs: 10_000,
      speed: 1
    });
    expect(playback.positionAt(50_000)).toBe(4_200);
  });

  it("measures ending animation time in real milliseconds", () => {
    const playback = new RemotePlayback();
    playback.apply({
      status: "playing",
      scoreId: "demo-score",
      durationMs: 16_000,
      positionMs: 14_000,
      anchorPositionMs: 14_000,
      anchorClockMs: 10_000,
      speed: 2
    });

    expect(playback.endingElapsedAt(10_999)).toBeUndefined();
    expect(playback.endingElapsedAt(11_000)).toBe(0);
    expect(playback.endingElapsedAt(11_750)).toBe(750);
  });

  it("does not start the ending animation while paused", () => {
    const playback = new RemotePlayback();
    playback.apply({
      status: "paused",
      scoreId: "demo-score",
      durationMs: 16_000,
      positionMs: 16_000,
      anchorPositionMs: 16_000,
      anchorClockMs: 10_000,
      speed: 1
    });

    expect(playback.endingElapsedAt(20_000)).toBeUndefined();
  });
});
