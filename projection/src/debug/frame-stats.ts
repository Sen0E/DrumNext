export interface FrameSnapshot {
  readonly fps: number;
  readonly frameTimeMs: number;
}

export class FrameStats {
  readonly #sampleWindowMs: number;
  #windowStartMs: number | undefined;
  #lastFrameMs: number | undefined;
  #frames = 0;
  #snapshot: FrameSnapshot = { fps: 0, frameTimeMs: 0 };

  constructor(sampleWindowMs = 500) {
    if (sampleWindowMs <= 0) throw new RangeError("sampleWindowMs must be positive");
    this.#sampleWindowMs = sampleWindowMs;
  }

  update(nowMs: number): FrameSnapshot {
    if (this.#windowStartMs === undefined) this.#windowStartMs = nowMs;
    if (this.#lastFrameMs !== undefined) {
      this.#snapshot = { ...this.#snapshot, frameTimeMs: nowMs - this.#lastFrameMs };
    }
    this.#lastFrameMs = nowMs;
    this.#frames += 1;

    const elapsedMs = nowMs - this.#windowStartMs;
    if (elapsedMs >= this.#sampleWindowMs) {
      this.#snapshot = { ...this.#snapshot, fps: (this.#frames * 1000) / elapsedMs };
      this.#windowStartMs = nowMs;
      this.#frames = 0;
    }
    return this.#snapshot;
  }
}

