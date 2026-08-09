import type { FrameSnapshot } from "./frame-stats";

export class PerformancePanel {
  readonly #element: HTMLDivElement;

  constructor() {
    this.#element = document.createElement("div");
    this.#element.className = "performance-panel";
    this.#element.textContent = "FPS --";
    document.body.append(this.#element);
  }

  update(snapshot: FrameSnapshot): void {
    this.#element.textContent = `FPS ${snapshot.fps.toFixed(1)}`;
  }

  destroy(): void {
    this.#element.remove();
  }
}
