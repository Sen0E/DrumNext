import { ClockSync } from "./clock-sync";
import { parseEnvelope, parsePlaybackSnapshot } from "./protocol";
import type { RemotePlayback } from "../playback/remote-playback";
import { ScheduledNoteStore } from "../playback/scheduled-notes";

const PLAYBACK_EVENTS = new Set([
  "playback.snapshot",
  "playback.started",
  "playback.paused",
  "playback.resumed",
  "playback.stopped",
  "playback.seeked",
  "playback.speed_changed",
  "score.changed"
]);

export class ProjectionSocket {
  readonly clock = new ClockSync();
  readonly scheduledNotes = new ScheduledNoteStore();
  #socket: WebSocket | undefined;
  #pingTimer: number | undefined;
  #reconnectTimer: number | undefined;
  #lastSequence = 0;
  #destroyed = false;

  constructor(
    readonly playback: RemotePlayback,
    readonly onContentChanged: () => void = () => undefined
  ) {}

  connect(): void {
    if (this.#destroyed) return;
    const scheme = window.location.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(`${scheme}//${window.location.host}/ws/v1/projection`);
    this.#socket = socket;
    socket.addEventListener("open", () => {
      this.#lastSequence = 0;
      this.#sendPing();
      this.#pingTimer = window.setInterval(() => this.#sendPing(), 2_000);
    });
    socket.addEventListener("message", (event) => this.#receive(event.data));
    socket.addEventListener("close", () => this.#scheduleReconnect());
    socket.addEventListener("error", () => socket.close());
  }

  destroy(): void {
    this.#destroyed = true;
    if (this.#pingTimer !== undefined) window.clearInterval(this.#pingTimer);
    if (this.#reconnectTimer !== undefined) window.clearTimeout(this.#reconnectTimer);
    this.#socket?.close();
  }

  #receive(raw: unknown): void {
    try {
      if (typeof raw !== "string") throw new Error("WebSocket message must be text");
      const receivedTimeMs = performance.now();
      const message = parseEnvelope(JSON.parse(raw) as unknown);
      this.clock.observeEnvelope(message.serverTimeMs, receivedTimeMs);
      if (message.sequence <= this.#lastSequence) return;
      this.#lastSequence = message.sequence;
      if (PLAYBACK_EVENTS.has(message.type)) {
        this.playback.apply(parsePlaybackSnapshot(message.payload));
        if (message.type === "score.changed") this.onContentChanged();
      } else if (message.type === "clock.pong") {
        const sentTimeMs = message.payload.clientTimeMs;
        if (typeof sentTimeMs === "number") {
          this.clock.addPingSample(sentTimeMs, receivedTimeMs, message.serverTimeMs);
        }
      } else if (message.type === "notes.scheduled") {
        this.#applyScheduledNotes(message.payload);
      } else if (
        message.type === "layout.changed"
        || message.type === "ending_animation.changed"
      ) {
        this.onContentChanged();
      }
    } catch (error: unknown) {
      console.error("projection.protocol_error", error);
    }
  }

  #applyScheduledNotes(payload: Record<string, unknown>): void {
    const scoreId = payload.scoreId;
    const notes = payload.notes;
    if (typeof scoreId !== "string" || !Array.isArray(notes)) {
      throw new Error("Invalid notes.scheduled payload");
    }
    const parsed = notes.map((value) => {
      if (typeof value !== "object" || value === null) throw new Error("Invalid scheduled note");
      const note = value as Record<string, unknown>;
      if (
        typeof note.id !== "string" ||
        typeof note.timeMs !== "number" ||
        typeof note.noteKey !== "string" ||
        typeof note.velocity !== "number"
      ) {
        throw new Error("Invalid scheduled note fields");
      }
      return { id: note.id, timeMs: note.timeMs, noteKey: note.noteKey, velocity: note.velocity };
    });
    this.scheduledNotes.apply(scoreId, parsed);
  }

  #sendPing(): void {
    if (this.#socket?.readyState !== WebSocket.OPEN) return;
    this.#socket.send(JSON.stringify({ type: "clock.ping", clientTimeMs: performance.now() }));
  }

  #scheduleReconnect(): void {
    if (this.#pingTimer !== undefined) window.clearInterval(this.#pingTimer);
    this.#pingTimer = undefined;
    if (!this.#destroyed) this.#reconnectTimer = window.setTimeout(() => this.connect(), 1_000);
  }
}
