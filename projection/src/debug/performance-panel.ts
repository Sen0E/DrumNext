import type { FrameSnapshot } from "./frame-stats";

export class PerformancePanel {
  readonly #element: HTMLDivElement;

  constructor(renderer: string) {
    this.#element = document.createElement("div");
    this.#element.className = "performance-panel";
    this.#element.textContent = `FPS -- | Frame -- ms | ${renderer}`;
    document.body.append(this.#element);
  }

  update(snapshot: FrameSnapshot): void {
    this.#element.textContent = `FPS ${snapshot.fps.toFixed(1)} | Frame ${snapshot.frameTimeMs.toFixed(2)} ms`;
  }

  destroy(): void {
    this.#element.remove();
  }
}

