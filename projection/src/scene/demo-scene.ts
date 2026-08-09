import { Container, Graphics, Text } from "pixi.js";
import type { DemoNote, PadConfig } from "../config/demo-content";
import { linearProgress, noteVisualState } from "../playback/timeline";
import {
  ENDING_ANIMATION_DURATION_MS,
  endingVisualState,
  segment,
  type EndingAnimationStyle,
  type EndingVisualState
} from "./ending-animation";
import {
  IDLE_COMET_COUNT,
  idleCometVisualState,
  idlePadVisualState,
  idleRippleVisualStates
} from "./idle-animation";
import type { SceneLayers } from "./layers";

const APPROACH_START_RADIUS = 180;
const PARTICLES_PER_PAD = 10;

interface PadView {
  readonly config: PadConfig;
  readonly x: number;
  readonly y: number;
  readonly radius: number;
  readonly group: Container;
  readonly idleFlow: Graphics;
  readonly idleCoreFlow: Graphics;
  readonly highlight: Graphics;
  readonly particles: readonly Graphics[];
}

interface IdleComet {
  readonly graphic: Graphics;
  readonly index: number;
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
  readonly #endingStarburst: Graphics;
  readonly #endingFlash: Graphics;
  readonly #endingStyle: EndingAnimationStyle;
  readonly #idleSeed: number;
  readonly #idleCenter: PadView | undefined;
  readonly #idleWave: Graphics;
  readonly #idleComets: readonly IdleComet[];
  readonly #width: number;
  readonly #height: number;

  constructor(
    layers: SceneLayers,
    pads: readonly PadConfig[],
    notes: readonly DemoNote[],
    durationMs: number,
    width: number,
    height: number,
    endingStyle: EndingAnimationStyle = "calm",
    idleSeed = 0
  ) {
    this.#durationMs = durationMs;
    this.#width = width;
    this.#height = height;
    this.#endingStyle = endingStyle;
    this.#idleSeed = idleSeed;
    this.#drawBackground(layers.background, width, height);
    this.#pads = new Map(pads.map((config) => {
      const pad = this.#createPad(layers, config, width, height);
      return [config.noteKey, pad];
    }));
    this.#idleCenter = this.#nearestPadToCenter(width, height);
    this.#idleWave = new Graphics();
    this.#idleWave.visible = false;
    this.#idleWave.blendMode = "add";
    layers.overlay.addChild(this.#idleWave);
    this.#idleComets = this.#createIdleComets(layers.overlay, pads);
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
    this.#endingStarburst = new Graphics();
    this.#endingStarburst.visible = false;
    this.#endingStarburst.blendMode = "add";
    this.#endingFlash = new Graphics()
      .rect(0, 0, width, height)
      .fill({ color: 0xe6f8ff });
    this.#endingFlash.visible = false;
    this.#endingFlash.blendMode = "add";
    layers.overlay.addChild(
      this.#endingRipple,
      this.#endingHalo,
      this.#endingStarburst,
      this.#endingFlash
    );
  }

  update(
    playbackTimeMs: number,
    endingElapsedMs?: number,
    idleElapsedMs?: number
  ): void {
    this.#resetVisuals();
    if (endingElapsedMs !== undefined) {
      if (endingElapsedMs >= ENDING_ANIMATION_DURATION_MS) {
        this.#updateIdle(endingElapsedMs - ENDING_ANIMATION_DURATION_MS);
        return;
      }
      this.#updateEnding(endingElapsedMs);
      return;
    }
    if (idleElapsedMs !== undefined) {
      this.#updateIdle(idleElapsedMs);
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
      pad.idleFlow.visible = false;
      pad.idleCoreFlow.visible = false;
      pad.highlight.visible = false;
      pad.highlight.scale.set(1);
      for (const particle of pad.particles) particle.visible = false;
    }
    for (const approach of this.#approaches) {
      approach.ring.visible = false;
    }
    this.#endingRipple.visible = false;
    this.#endingHalo.visible = false;
    this.#endingStarburst.visible = false;
    this.#endingFlash.visible = false;
    this.#idleWave.visible = false;
    for (const comet of this.#idleComets) comet.graphic.visible = false;
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
    const idleFlow = new Graphics()
      .arc(0, 0, radius * 1.1, -0.52, 1.58)
      .stroke({ width: 11, color: config.color });
    idleFlow.visible = false;
    idleFlow.blendMode = "add";
    const idleCoreFlow = new Graphics()
      .arc(0, 0, radius * 1.1, -0.28, 0.92)
      .stroke({ width: 4, color: 0xffffff });
    idleCoreFlow.visible = false;
    idleCoreFlow.blendMode = "add";
    group.addChild(face, inner, label, octave, idleFlow, idleCoreFlow);
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
    return {
      config,
      x,
      y,
      radius,
      group,
      idleFlow,
      idleCoreFlow,
      highlight,
      particles
    };
  }

  #createIdleComets(
    layer: Container,
    pads: readonly PadConfig[]
  ): readonly IdleComet[] {
    return Array.from({ length: IDLE_COMET_COUNT }, (_, index) => {
      const color = pads[index % pads.length]?.color ?? 0x82b7d8;
      const graphic = new Graphics();
      graphic.circle(0, 0, 6.5).fill({ color: 0xffffff, alpha: 0.96 });
      graphic.circle(-10, 0, 5.2).fill({ color, alpha: 0.8 });
      graphic.circle(-19, 0, 3.8).fill({ color, alpha: 0.58 });
      graphic.circle(-27, 0, 2.4).fill({ color, alpha: 0.34 });
      graphic.visible = false;
      graphic.blendMode = "add";
      layer.addChild(graphic);
      return { graphic, index };
    });
  }

  #updateIdle(elapsedMs: number): void {
    const centerX = this.#width / 2;
    const centerY = this.#height / 2;
    const distances = [...this.#pads.values()].map((pad) =>
      Math.hypot(pad.x - centerX, pad.y - centerY)
    );
    const maxDistance = Math.max(1, ...distances);
    for (const [index, pad] of [...this.#pads.values()].entries()) {
      const angle = Math.atan2(pad.y - centerY, pad.x - centerX);
      const clockwise = ((angle + Math.PI / 2 + Math.PI * 2) % (Math.PI * 2))
        / (Math.PI * 2);
      const distance = Math.hypot(pad.x - centerX, pad.y - centerY) / maxDistance;
      const state = idlePadVisualState(
        elapsedMs,
        index,
        clockwise,
        distance,
        pad === this.#idleCenter,
        this.#idleSeed
      );
      pad.group.scale.set(state.scale);
      pad.idleFlow.visible = state.flowAlpha > 0;
      pad.idleFlow.alpha = state.flowAlpha;
      pad.idleFlow.rotation = state.flowRotation;
      pad.idleCoreFlow.visible = state.coreFlowAlpha > 0;
      pad.idleCoreFlow.alpha = state.coreFlowAlpha;
      pad.idleCoreFlow.rotation = state.flowRotation;
      if (state.glowAlpha > 0) {
        pad.highlight.visible = true;
        pad.highlight.alpha = state.glowAlpha;
        pad.highlight.scale.set(1.04 + (state.scale - 1) * 2.1);
      }
    }

    const ripples = idleRippleVisualStates(elapsedMs);
    const center = this.#idleCenter;
    if (center !== undefined && ripples.some((ripple) => ripple.alpha > 0)) {
      this.#idleWave.clear();
      for (const ripple of ripples) {
        if (ripple.alpha <= 0) continue;
        const radius = center.radius
          + (maxDistance + center.radius) * ripple.progress;
        this.#idleWave
          .circle(center.x, center.y, radius)
          .stroke({ width: 12, color: center.config.color, alpha: ripple.alpha * 0.72 })
          .circle(center.x, center.y, radius)
          .stroke({ width: 4, color: 0xffffff, alpha: ripple.alpha });
      }
      this.#idleWave.visible = true;
    }

    for (const comet of this.#idleComets) {
      const state = idleCometVisualState(elapsedMs, comet.index, this.#idleSeed);
      comet.graphic.visible = state.alpha > 0;
      comet.graphic.alpha = state.alpha;
      comet.graphic.position.set(state.x * this.#width, state.y * this.#height);
      comet.graphic.scale.set(state.scale);
      comet.graphic.rotation = state.rotation;
    }
  }

  #updateEnding(elapsedMs: number): void {
    const state = endingVisualState(elapsedMs, this.#endingStyle);
    if (state.complete) return;

    if (state.style === "spectacular") {
      this.#updateSpectacularEnding(state);
      return;
    }

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

  #updateSpectacularEnding(state: EndingVisualState): void {
    const origin = this.#endingOrigin;
    if (origin !== undefined) {
      this.#drawSpectacularRipples(origin, state.elapsedMs);
    }

    const centerX = this.#width / 2;
    const centerY = this.#height / 2;
    for (const [padIndex, pad] of [...this.#pads.values()].entries()) {
      const angle = Math.atan2(pad.y - centerY, pad.x - centerX);
      const clockwise = ((angle + Math.PI / 2 + Math.PI * 2) % (Math.PI * 2))
        / (Math.PI * 2);
      const chaseProgress = segment(
        state.elapsedMs,
        280 + clockwise * 1_250,
        1_080 + clockwise * 1_250
      );
      const chase = Math.sin(Math.PI * chaseProgress);
      const resonance = state.resonance * 0.28;
      const lastGlow = pad === origin ? state.lastGlow : 0;
      const glow = Math.max(chase * 0.82, resonance, lastGlow);

      pad.group.alpha = state.drumAlpha;
      pad.group.scale.set(1 + chase * 0.075 + resonance * 0.025);
      if (glow > 0) {
        pad.highlight.visible = true;
        pad.highlight.alpha = glow * state.drumAlpha;
        pad.highlight.scale.set(1.08 + chase * 0.22 + lastGlow * 0.18);
      }
      if (state.gathering > 0 || state.burst > 0) {
        this.#animateSpectacularParticles(
          pad,
          padIndex,
          state.elapsedMs,
          centerX,
          centerY
        );
      }
    }

    if (state.haloAlpha > 0) {
      this.#endingHalo.visible = true;
      this.#endingHalo.alpha = state.haloAlpha * 0.42;
      this.#endingHalo.scale.set(0.55 + state.haloProgress * 2.1 + state.burst * 0.3);
    }
    if (state.burst > 0) this.#drawStarburst(state.burst, centerX, centerY);
    if (state.flash > 0) {
      this.#endingFlash.visible = true;
      this.#endingFlash.alpha = state.flash * 0.045;
    }
  }

  #drawSpectacularRipples(origin: PadView, elapsedMs: number): void {
    const colors = [...this.#pads.values()].map((pad) => pad.config.color);
    const maximumRadius = Math.hypot(this.#width, this.#height);
    this.#endingRipple.clear();
    let visible = false;
    for (let index = 0; index < 3; index += 1) {
      const progress = segment(elapsedMs, index * 240, 1_650 + index * 240);
      const alpha = Math.sin(Math.PI * progress) * (0.88 - index * 0.16);
      if (alpha <= 0) continue;
      const radius = origin.radius * (1 + index * 0.18)
        + (maximumRadius - origin.radius) * progress;
      this.#endingRipple
        .circle(origin.x, origin.y, radius)
        .stroke({
          width: 7 - index,
          color: colors[(index * 5) % colors.length] ?? origin.config.color,
          alpha
        });
      visible = true;
    }
    this.#endingRipple.visible = visible;
    this.#endingRipple.blendMode = "add";
  }

  #drawStarburst(amount: number, centerX: number, centerY: number): void {
    const colors = [...this.#pads.values()].map((pad) => pad.config.color);
    this.#endingStarburst.clear();
    for (let index = 0; index < 18; index += 1) {
      const angle = (index / 18) * Math.PI * 2;
      const innerRadius = 55 + (index % 3) * 14;
      const outerRadius = innerRadius + amount * (190 + (index % 4) * 38);
      this.#endingStarburst
        .moveTo(
          centerX + Math.cos(angle) * innerRadius,
          centerY + Math.sin(angle) * innerRadius
        )
        .lineTo(
          centerX + Math.cos(angle) * outerRadius,
          centerY + Math.sin(angle) * outerRadius
        )
        .stroke({
          width: index % 3 === 0 ? 5 : 3,
          color: colors[index % colors.length] ?? 0xffffff,
          alpha: amount * 0.72
        });
    }
    this.#endingStarburst.visible = true;
  }

  #animateSpectacularParticles(
    pad: PadView,
    padIndex: number,
    elapsedMs: number,
    centerX: number,
    centerY: number
  ): void {
    for (const [particleIndex, particle] of pad.particles.entries()) {
      const gatherDelay = (padIndex % 5) * 32 + (particleIndex % 4) * 48;
      const gather = segment(elapsedMs, 850 + gatherDelay, 3_050 + gatherDelay);
      const burstDelay = (particleIndex % 5) * 22;
      const burst = segment(elapsedMs, 3_120 + burstDelay, 4_150 + burstDelay);

      if (burst > 0 && burst < 1) {
        const angle = particleIndex * 2.399963 + padIndex * 0.73;
        const distance = burst * burst * (260 + (particleIndex % 4) * 115);
        particle.visible = true;
        particle.position.set(
          centerX + Math.cos(angle) * distance,
          centerY + Math.sin(angle) * distance
        );
        particle.alpha = (1 - burst) * 0.96;
        particle.scale.set(1.6 - burst * 0.9);
        continue;
      }
      if (gather <= 0 || gather >= 1) continue;

      const startAngle = particleIndex * 2.399963 + padIndex * 0.51;
      const startRadius = pad.radius * (0.25 + (particleIndex % 4) * 0.17);
      const startX = pad.x + Math.cos(startAngle) * startRadius;
      const startY = pad.y + Math.sin(startAngle) * startRadius;
      const initialAngle = Math.atan2(startY - centerY, startX - centerX);
      const initialRadius = Math.hypot(startX - centerX, startY - centerY);
      const direction = particleIndex % 2 === 0 ? 1 : -1;
      const spiralAngle = initialAngle + direction * gather * Math.PI * 2.4;
      const spiralRadius = initialRadius * (1 - gather * gather);

      particle.visible = true;
      particle.position.set(
        centerX + Math.cos(spiralAngle) * spiralRadius,
        centerY + Math.sin(spiralAngle) * spiralRadius
      );
      particle.alpha = Math.sin(Math.PI * gather) * 0.9;
      particle.scale.set(0.75 + gather * 0.85);
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
