export type PlaybackStatus = "stopped" | "playing" | "paused";

export interface PlaybackSnapshot {
  readonly status: PlaybackStatus;
  readonly scoreId: string;
  readonly durationMs: number;
  readonly positionMs: number;
  readonly anchorPositionMs: number;
  readonly anchorClockMs: number;
  readonly speed: number;
}

export interface EventEnvelope {
  readonly protocolVersion: 1;
  readonly type: string;
  readonly sequence: number;
  readonly serverTimeMs: number;
  readonly payload: Record<string, unknown>;
}

export function parseEnvelope(value: unknown): EventEnvelope {
  const object = record(value, "message");
  if (object.protocolVersion !== 1) throw new Error("Unsupported protocolVersion");
  const type = stringField(object, "type");
  const sequence = numberField(object, "sequence");
  const serverTimeMs = numberField(object, "serverTimeMs");
  const payload = record(object.payload, "payload");
  return { protocolVersion: 1, type, sequence, serverTimeMs, payload };
}

export function parsePlaybackSnapshot(payload: Record<string, unknown>): PlaybackSnapshot {
  const status = stringField(payload, "status");
  if (status !== "stopped" && status !== "playing" && status !== "paused") {
    throw new Error("Invalid playback status");
  }
  return {
    status,
    scoreId: stringField(payload, "scoreId"),
    durationMs: positiveField(payload, "durationMs"),
    positionMs: nonNegativeField(payload, "positionMs"),
    anchorPositionMs: nonNegativeField(payload, "anchorPositionMs"),
    anchorClockMs: nonNegativeField(payload, "anchorClockMs"),
    speed: positiveField(payload, "speed")
  };
}

function record(value: unknown, name: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${name} must be an object`);
  }
  return value as Record<string, unknown>;
}

function stringField(object: Record<string, unknown>, name: string): string {
  const value = object[name];
  if (typeof value !== "string" || value.length === 0) throw new Error(`${name} must be a string`);
  return value;
}

function numberField(object: Record<string, unknown>, name: string): number {
  const value = object[name];
  if (typeof value !== "number" || !Number.isFinite(value)) throw new Error(`${name} must be a number`);
  return value;
}

function nonNegativeField(object: Record<string, unknown>, name: string): number {
  const value = numberField(object, name);
  if (value < 0) throw new Error(`${name} must be non-negative`);
  return value;
}

function positiveField(object: Record<string, unknown>, name: string): number {
  const value = numberField(object, name);
  if (value <= 0) throw new Error(`${name} must be positive`);
  return value;
}

