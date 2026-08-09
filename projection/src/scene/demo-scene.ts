import { Container, Graphics, Text } from "pixi.js";
import type { DemoNote, PadConfig } from "../config/demo-content";
import { linearProgress, noteVisualState } from "../playback/timeline";
import type { SceneLayers } from "./layers";

const APPROACH_START_RADIUS = 180;
const PARTICLES_PER_PAD = 10;

interface PadView {
  readonly config: PadConfig;
  readonly x: number;
  readonly y: number;
  readonly radius: number;
  readonly highlight: Graphics;
  readonly particles: readonly Graphics[];
}

interface ApproachView {
  readonly note: DemoNote;
  readonly ring: Graphics;
  readonly pad: PadView;
}

export class DemoScene {
  readonly #durationMs: number;
  readonly #pads: ReadonlyMap<string, PadView>;
  readonly #approaches: readonly ApproachView[];

  constructor(
    layers: SceneLayers,
    pads: readonly PadConfig[],
    notes: readonly DemoNote[],
    durationMs: number,
    width: number,
    height: number
  ) {
    this.#durationMs = durationMs;
    this.#drawBackground(layers.background, width, height);
    this.#pads = new Map(pads.map((config) => {
      const pad = this.#createPad(layers, config, width, height);
      return [config.noteKey, pad];
    }));
    this.#approaches = notes.map((note) => {
      const pad = this.#pads.get(note.noteKey);
      if (pad === undefined) throw new Error(`Unknown noteKey: ${note.noteKey}`);
      const ring = new Graphics()
        .circle(0, 0, APPROACH_START_RADIUS)
        .stroke({ width: 7, color: pad.config.color });
      ring.position.set(pad.x, pad.y);
      ring.visible = false;
      layers.approaches.addChild(ring);
      return { note, ring, pad };
    });
  }

  update(playbackTimeMs: number): void {
    for (const pad of this.#pads.values()) {
      pad.highlight.visible = false;
      for (const particle of pad.particles) particle.visible = false;
    }

    for (const approach of this.#approaches) {
      const state = noteVisualState(playbackTimeMs, approach.note.timeMs, this.#durationMs);
      approach.ring.visible = state.approachVisible;
      if (state.approachVisible) {
        const progress = linearProgress(state.approachProgress);
        const radius = APPROACH_START_RADIUS + (approach.pad.radius - APPROACH_START_RADIUS) * progress;
        approach.ring.scale.set(radius / APPROACH_START_RADIUS);
        approach.ring.alpha = 0.22 + Math.max(0, (state.approachProgress - 0.8) / 0.2) * 0.78;
      }
      if (state.hitVisible) this.#updateHit(approach.pad, state.hitProgress, approach.note.velocity);
    }
  }

  #createPad(layers: SceneLayers, config: PadConfig, width: number, height: number): PadView {
    const x = config.x * width;
    const y = config.y * height;
    const radius = config.radius * height;
    const face = new Graphics()
      .circle(0, 0, radius)
      .fill({ color: 0x0d2034, alpha: 0.96 })
      .stroke({ width: 5, color: config.color, alpha: 0.85 });
    const inner = new Graphics().circle(0, 0, radius * 0.72).stroke({ width: 2, color: config.color, alpha: 0.25 });
    const label = new Text({
      text: config.label,
      style: { fill: 0xf4fbff, fontFamily: "sans-serif", fontSize: radius * 0.72, fontWeight: "600" }
    });
    label.anchor.set(0.5);
    const octave = new Text({
      text: config.octaveLabel,
      style: { fill: config.color, fontFamily: "sans-serif", fontSize: 18, fontWeight: "700" }
    });
    octave.anchor.set(0.5);
    octave.position.y = radius * 0.55;
    const group = new Container();
    group.position.set(x, y);
    group.addChild(face, inner, label, octave);
    layers.drums.addChild(group);

    const highlight = new Graphics().circle(0, 0, radius * 1.12).fill({ color: config.color });
    highlight.position.set(x, y);
    highlight.blendMode = "add";
    highlight.visible = false;
    layers.highlights.addChild(highlight);

    const particles = Array.from({ length: PARTICLES_PER_PAD }, (_, index) => {
      const particle = new Graphics().circle(0, 0, 3 + (index % 3) * 1.5).fill({ color: config.color });
      particle.visible = false;
      particle.blendMode = "add";
      layers.hits.addChild(particle);
      return particle;
    });
    return { config, x, y, radius, highlight, particles };
  }

  #updateHit(pad: PadView, progress: number, velocity: number): void {
    pad.highlight.visible = true;
    pad.highlight.alpha = (1 - progress) * 0.72 * velocity;
    pad.highlight.scale.set(1 + progress * 0.32);
    for (const [index, particle] of pad.particles.entries()) {
      const angle = index * 2.399963 + pad.x * 0.001;
      const distance = pad.radius * (0.35 + progress * (1.25 + (index % 4) * 0.16));
      particle.visible = true;
      particle.alpha = (1 - progress) ** 1.7 * velocity;
      particle.position.set(pad.x + Math.cos(angle) * distance, pad.y + Math.sin(angle) * distance);
      particle.scale.set(0.8 + progress * 1.4);
    }
  }

  #drawBackground(layer: Container, width: number, height: number): void {
    const backdrop = new Graphics().rect(0, 0, width, height).fill({ color: 0x000000 });
    layer.addChild(backdrop);
  }
}
