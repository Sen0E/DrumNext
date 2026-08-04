import { describe, expect, it } from "vitest";
import { ScheduledNoteStore } from "../src/playback/scheduled-notes";

describe("ScheduledNoteStore", () => {
  it("deduplicates overlapping windows by note id", () => {
    const store = new ScheduledNoteStore();
    const note = { id: "n-1", timeMs: 1_000, noteKey: "low_1", velocity: 1 };
    store.apply("score-a", [note]);
    store.apply("score-a", [note]);
    expect(store.notes).toEqual([note]);
  });

  it("clears old notes when the score changes", () => {
    const store = new ScheduledNoteStore();
    store.apply("score-a", [{ id: "a", timeMs: 100, noteKey: "low_1", velocity: 1 }]);
    store.apply("score-b", [{ id: "b", timeMs: 200, noteKey: "mid_1", velocity: 0.8 }]);
    expect(store.notes.map((note) => note.id)).toEqual(["b"]);
  });
});
