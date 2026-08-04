interface ClockSample {
  readonly roundTripMs: number;
  readonly offsetMs: number;
}

export class ClockSync {
  readonly #samples: ClockSample[] = [];
  #offsetMs = 0;
  #initialized = false;

  observeEnvelope(serverTimeMs: number, receivedTimeMs: number): void {
    if (!this.#initialized) {
      this.#offsetMs = serverTimeMs - receivedTimeMs;
      this.#initialized = true;
    }
  }

  addPingSample(sentTimeMs: number, receivedTimeMs: number, serverTimeMs: number): void {
    const roundTripMs = receivedTimeMs - sentTimeMs;
    if (roundTripMs < 0 || roundTripMs > 2_000) return;
    const midpointMs = sentTimeMs + roundTripMs / 2;
    this.#samples.push({ roundTripMs, offsetMs: serverTimeMs - midpointMs });
    if (this.#samples.length > 12) this.#samples.shift();

    const lowLatency = [...this.#samples]
      .sort((left, right) => left.roundTripMs - right.roundTripMs)
      .slice(0, Math.max(1, Math.ceil(this.#samples.length / 2)))
      .map((sample) => sample.offsetMs)
      .sort((left, right) => left - right);
    const estimate = lowLatency[Math.floor(lowLatency.length / 2)];
    if (estimate !== undefined) {
      this.#offsetMs = this.#initialized ? this.#offsetMs * 0.8 + estimate * 0.2 : estimate;
      this.#initialized = true;
    }
  }

  serverTime(localTimeMs: number): number {
    return localTimeMs + this.#offsetMs;
  }

  get offsetMs(): number {
    return this.#offsetMs;
  }
}

