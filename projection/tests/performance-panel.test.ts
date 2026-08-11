import { afterEach, describe, expect, it, vi } from "vitest";
import { PerformancePanel } from "../src/debug/performance-panel";

afterEach(() => vi.unstubAllGlobals());

describe("PerformancePanel", () => {
  it("is hidden by default and can be shown at runtime", () => {
    const element = {
      className: "",
      hidden: false,
      textContent: "",
      remove: vi.fn()
    };
    const append = vi.fn();
    vi.stubGlobal("document", {
      createElement: vi.fn(() => element),
      body: { append }
    });

    const panel = new PerformancePanel();
    expect(element.hidden).toBe(true);
    expect(append).toHaveBeenCalledWith(element);

    panel.setVisible(true);
    panel.update({ fps: 59.8, frameTimeMs: 16.7 });
    expect(element.hidden).toBe(false);
    expect(element.textContent).toBe("FPS 59.8");

    panel.destroy();
    expect(element.remove).toHaveBeenCalledOnce();
  });
});
