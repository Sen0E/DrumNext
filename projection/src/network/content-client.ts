import type { DemoNote, PadConfig } from "../config/demo-content";
import type { ProjectionVisualSettings } from "../config/projection-visual-settings";
import type { EndingAnimationStyle } from "../scene/ending-animation";
import { parsePlaybackSnapshot } from "./protocol";
import type { PlaybackSnapshot } from "./protocol";

interface ScoreResponse {
  readonly id: string;
  readonly durationMs: number;
  readonly notes: readonly DemoNote[];
}

export interface LoadedContent {
  readonly playback: PlaybackSnapshot;
  readonly durationMs: number;
  readonly notes: readonly DemoNote[];
  readonly pads: readonly PadConfig[];
  readonly endingAnimationStyle: EndingAnimationStyle;
  readonly projectionVisualSettings: ProjectionVisualSettings;
}

export class ContentClient {
  async load(): Promise<LoadedContent> {
    const [
      playbackValue,
      layoutValue,
      endingAnimationValue,
      projectionVisualsValue
    ] = await Promise.all([
      this.#json("/api/v1/playback"),
      this.#json("/api/v1/layout"),
      this.#json("/api/v1/settings/ending-animation"),
      this.#json("/api/v1/settings/projection-visuals")
    ]);
    const playback = parsePlaybackSnapshot(asRecord(playbackValue));
    const scoreValue = await this.#json(`/api/v1/scores/${encodeURIComponent(playback.scoreId)}`);
    const score = parseScore(asRecord(scoreValue));
    const pads = parseLayout(asRecord(layoutValue));
    const endingAnimationStyle = parseEndingAnimation(asRecord(endingAnimationValue));
    const projectionVisualSettings = parseProjectionVisualSettings(
      asRecord(projectionVisualsValue)
    );
    const padKeys = new Set(pads.map((pad) => pad.noteKey));
    if (score.notes.some((note) => !padKeys.has(note.noteKey))) {
      throw new Error("乐谱包含布局中不存在的 noteKey");
    }
    return {
      playback,
      durationMs: score.durationMs,
      notes: score.notes,
      pads,
      endingAnimationStyle,
      projectionVisualSettings
    };
  }

  async #json(path: string): Promise<unknown> {
    const response = await fetch(path);
    if (!response.ok) throw new Error(`资源请求失败：${path} (${String(response.status)})`);
    return await response.json() as unknown;
  }
}

function parseProjectionVisualSettings(
  value: Record<string, unknown>
): ProjectionVisualSettings {
  const showPerformanceInfo = value.showPerformanceInfo;
  if (typeof showPerformanceInfo !== "boolean") {
    throw new Error("无效的性能信息显示设置");
  }
  const approachRingWidth = finiteNumber(value, "approachRingWidth");
  const approachRingOpacity = finiteNumber(value, "approachRingOpacity");
  const lowPadScale = finiteNumber(value, "lowPadScale");
  const midPadScale = finiteNumber(value, "midPadScale");
  const highPadScale = finiteNumber(value, "highPadScale");
  const centerPadScale = finiteNumber(value, "centerPadScale");
  if (approachRingWidth < 2 || approachRingWidth > 40) {
    throw new Error("无效的缩圈线宽");
  }
  if (approachRingOpacity < 0.05 || approachRingOpacity > 1) {
    throw new Error("无效的缩圈透明度");
  }
  if ([lowPadScale, midPadScale, highPadScale, centerPadScale].some(
    (scale) => scale < 0.5 || scale > 2
  )) {
    throw new Error("无效的鼓面尺寸倍率");
  }
  return {
    showPerformanceInfo,
    approachRingWidth,
    approachRingOpacity,
    lowPadScale,
    midPadScale,
    highPadScale,
    centerPadScale
  };
}

function parseEndingAnimation(value: Record<string, unknown>): EndingAnimationStyle {
  if (value.style !== "calm" && value.style !== "spectacular") {
    throw new Error("无效的结束动画风格");
  }
  return value.style;
}

function parseScore(value: Record<string, unknown>): ScoreResponse {
  if (typeof value.id !== "string" || typeof value.durationMs !== "number" || !Array.isArray(value.notes)) {
    throw new Error("无效的乐谱响应");
  }
  const notes = value.notes.map((raw) => {
    const note = asRecord(raw);
    if (
      typeof note.id !== "string" ||
      typeof note.timeMs !== "number" ||
      typeof note.noteKey !== "string" ||
      typeof note.velocity !== "number"
    ) throw new Error("无效的乐谱音符");
    return { id: note.id, timeMs: note.timeMs, noteKey: note.noteKey, velocity: note.velocity };
  });
  return { id: value.id, durationMs: value.durationMs, notes };
}

function parseLayout(value: Record<string, unknown>): readonly PadConfig[] {
  if (!Array.isArray(value.pads)) throw new Error("无效的布局响应");
  return value.pads.map((raw) => {
    const pad = asRecord(raw);
    if (
      typeof pad.noteKey !== "string" || typeof pad.x !== "number" ||
      typeof pad.y !== "number" || typeof pad.radius !== "number" ||
      typeof pad.color !== "string" || typeof pad.label !== "string" ||
      typeof pad.octaveLabel !== "string"
    ) throw new Error("无效的布局鼓面");
    return {
      noteKey: pad.noteKey,
      x: pad.x,
      y: pad.y,
      radius: pad.radius,
      color: parseColor(pad.color),
      label: pad.label,
      octaveLabel: pad.octaveLabel
    };
  });
}

function parseColor(value: string): number {
  if (!/^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$/.test(value)) throw new Error("无效的布局颜色");
  return Number.parseInt(value.slice(1, 7), 16);
}

function finiteNumber(value: Record<string, unknown>, name: string): number {
  const field = value[name];
  if (typeof field !== "number" || !Number.isFinite(field)) {
    throw new Error(`无效的投影视觉参数：${name}`);
  }
  return field;
}

function asRecord(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error("响应必须是对象");
  return value as Record<string, unknown>;
}
