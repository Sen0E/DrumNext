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
});
