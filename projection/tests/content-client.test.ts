import { afterEach, describe, expect, it, vi } from "vitest";
import { ContentClient } from "../src/network/content-client";

const playback = {
  status: "stopped", scoreId: "score-a", durationMs: 2_000, positionMs: 0,
  anchorPositionMs: 0, anchorClockMs: 10, speed: 1
};
const score = {
  id: "score-a", durationMs: 2_000,
  notes: [{ id: "n-1", timeMs: 500, noteKey: "low_1", velocity: 0.8 }]
};
const layout = {
  pads: [{ noteKey: "low_1", x: 0.5, y: 0.5, radius: 0.05, color: "#45A3FF", label: "1", octaveLabel: "L" }]
};

afterEach(() => vi.unstubAllGlobals());

describe("ContentClient", () => {
  it("loads playback, selected score and layout from FastAPI", async () => {
    vi.stubGlobal("fetch", vi.fn((path: string) => {
      const body = path.includes("scores") ? score : path.includes("layout") ? layout : playback;
      return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
    }));
    const content = await new ContentClient().load();
    expect(content.notes[0]?.id).toBe("n-1");
    expect(content.pads[0]?.color).toBe(0x45a3ff);
  });

  it("rejects a score note absent from the layout", async () => {
    vi.stubGlobal("fetch", vi.fn((path: string) => {
      const body = path.includes("scores") ? { ...score, notes: [{ ...score.notes[0], noteKey: "high_7" }] } : path.includes("layout") ? layout : playback;
      return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
    }));
    await expect(new ContentClient().load()).rejects.toThrow("noteKey");
  });
});
