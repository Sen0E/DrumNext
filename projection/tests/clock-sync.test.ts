import { describe, expect, it } from "vitest";
import { ClockSync } from "../src/network/clock-sync";

describe("ClockSync", () => {
  it("uses an envelope for the initial estimate", () => {
    const sync = new ClockSync();
    sync.observeEnvelope(12_000, 2_000);
    expect(sync.serverTime(2_500)).toBe(12_500);
  });

  it("prefers low-latency ping samples and smooths corrections", () => {
    const sync = new ClockSync();
    sync.observeEnvelope(11_000, 1_000);
    sync.addPingSample(2_000, 2_020, 12_010);
    sync.addPingSample(3_000, 3_400, 15_000);
    expect(sync.offsetMs).toBeCloseTo(10_000);
  });
});

