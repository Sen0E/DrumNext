export const IDLE_FADE_IN_MS = 1_500;
export const IDLE_CYCLE_MS = 8_000;
export const IDLE_COMET_COUNT = 8;
export const IDLE_RIPPLE_COUNT = 3;

const CHASE_START_MS = 3_500;
const CHASE_DURATIONS_MS = [1_900, 2_350, 2_800] as const;
const CHASE_START_STEPS = [1, 2, 4, 7, 8, 11, 13, 14] as const;

export interface IdlePadVisualState {
  readonly scale: number;
  readonly glowAlpha: number;
  readonly flowAlpha: number;
  readonly coreFlowAlpha: number;
  readonly flowRotation: number;
}

export interface IdleWaveVisualState {
  readonly progress: number;
  readonly alpha: number;
}

export interface IdleCometVisualState {
  readonly x: number;
  readonly y: number;
  readonly alpha: number;
  readonly scale: number;
  readonly rotation: number;
}

export interface IdleCycleVariant {
  readonly direction: -1 | 1;
  readonly startPosition: number;
  readonly chaseDurationMs: number;
  readonly dualChase: boolean;
}

export function idlePadVisualState(
  elapsedMs: number,
  index: number,
  clockwisePosition = index / 15,
  radialDistance = 0.5,
  isCenter = false,
  seed = 0
): IdlePadVisualState {
  const strength = idleStrength(elapsedMs);
  const cycle = cycleTime(elapsedMs);
  const centerCharge = isCenter ? pulse(cycle, 450, 1_650) : 0;
  const rippleHit = Math.max(0, ...idleRippleVisualStates(elapsedMs).map((ripple) =>
    Math.max(0, 1 - Math.abs(ripple.progress - radialDistance) / 0.14) * ripple.alpha
  ));
  const variant = idleCycleVariant(elapsedMs, seed);
  const primaryOrder = chaseOrder(clockwisePosition, variant);
  const primary = pulse(
    cycle,
    CHASE_START_MS + primaryOrder * variant.chaseDurationMs,
    CHASE_START_MS + primaryOrder * variant.chaseDurationMs + 820
  );
  const secondaryOrder = modulo(primaryOrder + 0.5, 1);
  const secondary = variant.dualChase
    ? pulse(
      cycle,
      CHASE_START_MS + secondaryOrder * variant.chaseDurationMs,
      CHASE_START_MS + secondaryOrder * variant.chaseDurationMs + 760
    ) * 0.86
    : 0;
  const patrol = Math.max(primary, secondary);
  const energy = Math.max(centerCharge, rippleHit, patrol);

  return {
    scale: 1 + strength * (
      centerCharge * 0.06
      + rippleHit * 0.045
      + patrol * 0.055
    ),
    glowAlpha: strength * Math.min(0.9, energy * 0.78 + rippleHit * 0.16),
    flowAlpha: strength * Math.min(0.92, patrol * 0.84 + rippleHit * 0.58),
    coreFlowAlpha: strength * Math.min(0.95, patrol * 0.9 + rippleHit * 0.68),
    flowRotation: clockwisePosition * Math.PI * 2
      + variant.direction * cycle / 900
      + variant.startPosition * Math.PI * 2
  };
}

export function idleRippleVisualStates(elapsedMs: number): readonly IdleWaveVisualState[] {
  const cycle = cycleTime(elapsedMs);
  const strength = idleStrength(elapsedMs);
  return Array.from({ length: IDLE_RIPPLE_COUNT }, (_, index) => {
    const startMs = 1_050 + index * 360;
    const endMs = startMs + 3_100;
    const linearProgress = segment(cycle, startMs, endMs);
    const active = cycle > startMs && cycle < endMs;
    return {
      progress: smoothstep(linearProgress),
      alpha: active
        ? strength * Math.sin(Math.PI * linearProgress) * (0.88 - index * 0.08)
        : 0
    };
  });
}

export function idleWaveVisualState(elapsedMs: number): IdleWaveVisualState {
  return idleRippleVisualStates(elapsedMs)[0] ?? { progress: 0, alpha: 0 };
}

export function idleCycleVariant(elapsedMs: number, seed = 0): IdleCycleVariant {
  const cycleIndex = Math.max(0, Math.floor(elapsedMs / IDLE_CYCLE_MS));
  return baseVariant(cycleIndex, seed);
}

export function idleCometVisualState(
  elapsedMs: number,
  index: number,
  seed = 0
): IdleCometVisualState {
  const cycle = cycleTime(elapsedMs);
  const cycleIndex = Math.max(0, Math.floor(elapsedMs / IDLE_CYCLE_MS));
  const variant = idleCycleVariant(elapsedMs, seed);
  const cometProgress = index / Math.max(1, IDLE_COMET_COUNT - 1);
  const jitter = unitRandom(seed, cycleIndex, 10 + index);
  const startMs = CHASE_START_MS
    + cometProgress * variant.chaseDurationMs * 0.62
    + jitter * 160;
  const progress = segment(cycle, startMs, startMs + 1_350);
  const active = cycle > startMs && cycle < startMs + 1_350;
  const secondRoute = variant.dualChase && index % 2 === 1;
  const phase = variant.startPosition * Math.PI * 2
    + (secondRoute ? Math.PI : 0)
    + variant.direction * cometProgress * 0.7;
  const angle = phase + variant.direction * progress * 1.2;
  const radius = 0.15 + progress * 0.37;

  return {
    x: 0.5 + Math.cos(angle) * radius,
    y: 0.5 + Math.sin(angle) * radius * 0.72,
    alpha: active
      ? idleStrength(elapsedMs) * Math.sin(Math.PI * progress) * 0.92
      : 0,
    scale: 0.85 + Math.sin(Math.PI * progress) * 0.5,
    rotation: angle + (variant.direction > 0 ? 0.78 : Math.PI - 0.78)
  };
}

export function idleStrength(elapsedMs: number): number {
  return smoothstep(Math.min(1, Math.max(0, elapsedMs / IDLE_FADE_IN_MS)));
}

function baseVariant(cycleIndex: number, seed: number): IdleCycleVariant {
  const speedIndex = Math.floor(unitRandom(seed, cycleIndex, 2) * CHASE_DURATIONS_MS.length);
  const startOffset = Math.floor(unitRandom(seed, 0, 20) * 15);
  const startStepIndex = Math.floor(unitRandom(seed, 0, 21) * CHASE_START_STEPS.length);
  const startStep = CHASE_START_STEPS[startStepIndex] ?? CHASE_START_STEPS[0];
  return {
    direction: unitRandom(seed, cycleIndex, 0) < 0.5 ? -1 : 1,
    startPosition: ((startOffset + cycleIndex * startStep) % 15) / 15,
    chaseDurationMs: CHASE_DURATIONS_MS[speedIndex] ?? CHASE_DURATIONS_MS[1],
    dualChase: unitRandom(seed, cycleIndex, 3) > 0.72
  };
}

function chaseOrder(clockwisePosition: number, variant: IdleCycleVariant): number {
  return variant.direction > 0
    ? modulo(clockwisePosition - variant.startPosition, 1)
    : modulo(variant.startPosition - clockwisePosition, 1);
}

function unitRandom(seed: number, cycleIndex: number, channel: number): number {
  let value = (seed >>> 0)
    ^ Math.imul(cycleIndex + 1, 0x9e3779b1)
    ^ Math.imul(channel + 1, 0x85ebca6b);
  value = Math.imul(value ^ (value >>> 16), 0x7feb352d);
  value = Math.imul(value ^ (value >>> 15), 0x846ca68b);
  return ((value ^ (value >>> 16)) >>> 0) / 0x1_0000_0000;
}

function cycleTime(elapsedMs: number): number {
  return modulo(elapsedMs, IDLE_CYCLE_MS);
}

function pulse(value: number, start: number, end: number): number {
  if (value <= start || value >= end) return 0;
  return Math.sin(Math.PI * segment(value, start, end));
}

function segment(value: number, start: number, end: number): number {
  return Math.min(1, Math.max(0, (value - start) / (end - start)));
}

function smoothstep(value: number): number {
  return value * value * (3 - 2 * value);
}

function modulo(value: number, divisor: number): number {
  return ((value % divisor) + divisor) % divisor;
}
