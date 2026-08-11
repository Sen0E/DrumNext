import type { FrameSnapshot } from "./frame-stats";

export class PerformancePanel {
  readonly #element: HTMLDivElement;

  constructor(visible = false) {
    this.#element = document.createElement("div");
    this.#element.className = "performance-panel";
    this.#element.textContent = "FPS --";
    this.setVisible(visible);
    document.body.append(this.#element);
  }

  setVisible(visible: boolean): void {
    this.#element.hidden = !visible;
  }

  update(snapshot: FrameSnapshot): void {
    this.#element.textContent = `FPS ${snapshot.fps.toFixed(1)}`;
  }

  destroy(): void {
    this.#element.remove();
  }
}
