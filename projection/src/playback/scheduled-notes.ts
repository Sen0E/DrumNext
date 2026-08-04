export interface ScheduledNote {
  readonly id: string;
  readonly timeMs: number;
  readonly noteKey: string;
  readonly velocity: number;
}

export class ScheduledNoteStore {
  #scoreId: string | undefined;
  readonly #notes = new Map<string, ScheduledNote>();

  apply(scoreId: string, notes: readonly ScheduledNote[]): void {
    if (scoreId !== this.#scoreId) {
      this.#scoreId = scoreId;
      this.#notes.clear();
    }
    for (const note of notes) this.#notes.set(note.id, note);
  }

  clearBefore(timeMs: number): void {
    for (const [id, note] of this.#notes) {
      if (note.timeMs < timeMs) this.#notes.delete(id);
    }
  }

  get notes(): readonly ScheduledNote[] {
    return [...this.#notes.values()].sort((left, right) => left.timeMs - right.timeMs);
  }
}

