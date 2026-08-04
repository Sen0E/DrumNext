import { Container } from "pixi.js";

export interface SceneLayers {
  readonly root: Container;
  readonly background: Container;
  readonly drums: Container;
  readonly highlights: Container;
  readonly approaches: Container;
  readonly hits: Container;
  readonly overlay: Container;
  readonly debug: Container;
}

export function createSceneLayers(): SceneLayers {
  const root = new Container({ label: "SceneRoot" });
  const background = new Container({ label: "BackgroundLayer" });
  const drums = new Container({ label: "DrumLayer" });
  const highlights = new Container({ label: "HighlightLayer" });
  const approaches = new Container({ label: "ApproachLayer" });
  const hits = new Container({ label: "HitEffectLayer" });
  const overlay = new Container({ label: "OverlayLayer" });
  const debug = new Container({ label: "DebugLayer" });
  root.addChild(background, drums, highlights, approaches, hits, overlay, debug);
  return { root, background, drums, highlights, approaches, hits, overlay, debug };
}

