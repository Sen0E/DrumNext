import { Container, Graphics, Text } from "pixi.js";
import type { DemoNote, PadConfig } from "../config/demo-content";
import { linearProgress, noteVisualState } from "../playback/timeline";
import { endingVisualState, segment } from "./ending-animation";
import type { SceneLayers } from "./layers";

const APPROACH_START_RADIUS = 180;
const PARTICLES_PER_PAD = 10;

interface PadView {
  readonly config: PadConfig;
  readonly x: number;
  readonly y: number;
  readonly radius: number;
  readonly group: Container;
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
  readonly #endingOrigin: PadView | undefined;
  readonly #endingRipple: Graphics;
  readonly #endingHalo: Graphics;
  readonly #width: number;
  readonly #height: number;

  constructor(
    layers: SceneLayers,
    pads: readonly PadConfig[],
    notes: readonly DemoNote[],
    durationMs: number,
    width: number,
    height: number
  ) {
    this.#durationMs = durationMs;
    this.#width = width;
    this.#height = height;
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
    const lastNote = notes.at(-1);
    this.#endingOrigin = lastNote === undefined
      ? this.#nearestPadToCenter(width, height)
      : this.#pads.get(lastNote.noteKey);
    const endingColor = this.#endingOrigin?.config.color ?? 0x82b7d8;
    this.#endingRipple = new Graphics();
    this.#endingRipple.visible = false;
    this.#endingHalo = new Graphics()
      .circle(0, 0, 110)
      .fill({ color: endingColor });
    this.#endingHalo.position.set(width / 2, height / 2);
    this.#endingHalo.visible = false;
    this.#endingHalo.blendMode = "add";
    layers.overlay.addChild(this.#endingRipple, this.#endingHalo);
  }

  update(playbackTimeMs: number, endingElapsedMs?: number): void {
    this.#resetVisuals();
    if (endingElapsedMs !== undefined) {
      this.#updateEnding(endingElapsedMs);
      return;
    }
    if (playbackTimeMs >= this.#durationMs) return;

    this.#updateNotes(playbackTimeMs);
  }

  #updateNotes(playbackTimeMs: number): void {
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

  #resetVisuals(): void {
    for (const pad of this.#pads.values()) {
      pad.group.alpha = 1;
      pad.group.scale.set(1);
      pad.highlight.visible = false;
      pad.highlight.scale.set(1);
      for (const particle of pad.particles) particle.visible = false;
    }
    for (const approach of this.#approaches) {
      approach.ring.visible = false;
    }
    this.#endingRipple.visible = false;
    this.#endingHalo.visible = false;
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
    return { config, x, y, radius, group, highlight, particles };
  }

  #updateEnding(elapsedMs: number): void {
    const state = endingVisualState(elapsedMs);
    if (state.complete) return;

    const origin = this.#endingOrigin;
    if (origin !== undefined) {
      this.#drawEndingRipple(origin, state.rippleProgress, state.rippleAlpha);
    }

    const centerX = this.#width / 2;
    const centerY = this.#height / 2;
    const maxDistance = Math.hypot(centerX, centerY);
    for (const [padIndex, pad] of [...this.#pads.values()].entries()) {
      const distance = Math.hypot(pad.x - centerX, pad.y - centerY) / maxDistance;
      const resonanceProgress = segment(elapsedMs, 650 + distance * 550, 1_650 + distance * 550);
      const resonance = Math.sin(Math.PI * resonanceProgress) * state.resonance;
      pad.group.alpha = state.drumAlpha;
      pad.group.scale.set(1 + resonance * 0.035);

      const lastGlow = pad === origin ? state.lastGlow : 0;
      const glow = Math.max(lastGlow * 0.75, resonance * 0.2);
      if (glow > 0) {
        pad.highlight.visible = true;
        pad.highlight.alpha = glow * state.drumAlpha;
        pad.highlight.scale.set(1 + lastGlow * 0.2 + resonance * 0.08);
      }
      if (state.gathering > 0) {
        this.#gatherParticles(pad, padIndex, elapsedMs, centerX, centerY);
      }
    }

    if (state.haloAlpha > 0) {
      this.#endingHalo.visible = true;
      this.#endingHalo.alpha = state.haloAlpha;
      this.#endingHalo.scale.set(0.65 + state.haloProgress * 1.15);
    }
  }

  #drawEndingRipple(origin: PadView, progress: number, alpha: number): void {
    if (alpha <= 0) return;
    const radius = origin.radius * 1.1
      + (Math.hypot(this.#width, this.#height) - origin.radius) * progress;
    this.#endingRipple
      .clear()
      .circle(origin.x, origin.y, radius)
      .stroke({ width: 5, color: origin.config.color, alpha });
    this.#endingRipple.visible = true;
    this.#endingRipple.blendMode = "add";
  }

  #gatherParticles(
    pad: PadView,
    padIndex: number,
    elapsedMs: number,
    centerX: number,
    centerY: number
  ): void {
    for (const [particleIndex, particle] of pad.particles.entries()) {
      const delayMs = (padIndex % 5) * 35 + (particleIndex % 4) * 55;
      const progress = segment(elapsedMs, 1_450 + delayMs, 3_550 + delayMs);
      if (progress <= 0 || progress >= 1) continue;

      const angle = particleIndex * 2.399963 + padIndex * 0.71;
      const startDistance = pad.radius * (0.28 + (particleIndex % 4) * 0.16);
      const startX = pad.x + Math.cos(angle) * startDistance;
      const startY = pad.y + Math.sin(angle) * startDistance;
      const eased = progress * progress * (3 - 2 * progress);
      const dx = centerX - startX;
      const dy = centerY - startY;
      const distance = Math.max(1, Math.hypot(dx, dy));
      const arc = Math.sin(Math.PI * progress) * pad.radius * (0.7 + (particleIndex % 3) * 0.22);
      const direction = particleIndex % 2 === 0 ? 1 : -1;

      particle.visible = true;
      particle.position.set(
        startX + dx * eased - (dy / distance) * arc * direction,
        startY + dy * eased + (dx / distance) * arc * direction
      );
      particle.alpha = Math.sin(Math.PI * progress) * 0.72;
      particle.scale.set(0.65 + (1 - progress) * 0.75);
    }
  }

  #nearestPadToCenter(width: number, height: number): PadView | undefined {
    const centerX = width / 2;
    const centerY = height / 2;
    return [...this.#pads.values()].sort((left, right) =>
      Math.hypot(left.x - centerX, left.y - centerY)
      - Math.hypot(right.x - centerX, right.y - centerY)
    )[0];
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
