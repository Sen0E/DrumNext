import { Application } from "pixi.js";
import { detectWebGl2 } from "./app/webgl";
import { FrameStats } from "./debug/frame-stats";
import { PerformancePanel } from "./debug/performance-panel";
import { ContentClient } from "./network/content-client";
import { ProjectionSocket } from "./network/projection-socket";
import { RemotePlayback } from "./playback/remote-playback";
import { DemoScene } from "./scene/demo-scene";
import { createSceneLayers } from "./scene/layers";
import "./style.css";

const DESIGN_WIDTH = 1920;
const DESIGN_HEIGHT = 1080;

async function start(): Promise<void> {
  const host = document.querySelector<HTMLElement>("#app");
  const status = document.querySelector<HTMLElement>("#status");
  if (host === null || status === null) throw new Error("Projection host is missing");

  const capability = detectWebGl2();
  if (!capability.supported) {
    status.className = "fatal-status";
    status.textContent = `无法启动投影：${capability.reason}`;
    return;
  }

  const app = new Application();
  await app.init({
    width: DESIGN_WIDTH,
    height: DESIGN_HEIGHT,
    resolution: 1,
    autoDensity: false,
    background: "#000000",
    preference: "webgl",
    antialias: true
  });
  app.canvas.setAttribute("aria-label", "DrumNext WebGL2 场景");
  host.replaceChildren(app.canvas);

  let layers = createSceneLayers();
  app.stage.addChild(layers.root);
  const contentClient = new ContentClient();
  const remotePlayback = new RemotePlayback();
  const initialContent = await contentClient.load();
  remotePlayback.apply(initialContent.playback);
  let scene = new DemoScene(layers, initialContent.pads, initialContent.notes, initialContent.durationMs, DESIGN_WIDTH, DESIGN_HEIGHT);
  const fixedTimeParameter = new URLSearchParams(window.location.search).get("timeMs");
  const fixedTimeMs = fixedTimeParameter === null ? undefined : Number(fixedTimeParameter);
  if (fixedTimeMs !== undefined && Number.isFinite(fixedTimeMs)) {
    document.body.classList.add("fixed-preview");
    scene.update(fixedTimeMs);
  }
  let reloadVersion = 0;
  const reloadContent = (): void => {
    const requestedVersion = ++reloadVersion;
    void contentClient.load().then((content) => {
      if (requestedVersion !== reloadVersion) return;
      layers.root.destroy({ children: true });
      const replacementLayers = createSceneLayers();
      app.stage.addChild(replacementLayers.root);
      layers = replacementLayers;
      remotePlayback.apply(content.playback);
      scene = new DemoScene(replacementLayers, content.pads, content.notes, content.durationMs, DESIGN_WIDTH, DESIGN_HEIGHT);
    }).catch((error: unknown) => console.error("projection.content_reload_failed", error));
  };
  const projectionSocket = new ProjectionSocket(remotePlayback, reloadContent);
  if (fixedTimeMs === undefined || !Number.isFinite(fixedTimeMs)) projectionSocket.connect();
  window.addEventListener("beforeunload", () => projectionSocket.destroy(), { once: true });

  const stats = new FrameStats();
  const panel = new PerformancePanel();
  app.ticker.add(() => {
    const nowMs = performance.now();
    if (fixedTimeMs === undefined || !Number.isFinite(fixedTimeMs)) {
      const serverTimeMs = projectionSocket.clock.serverTime(nowMs);
      scene.update(
        remotePlayback.positionAt(serverTimeMs),
        remotePlayback.endingElapsedAt(serverTimeMs)
      );
    }
    panel.update(stats.update(nowMs));
  });
}

void start().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : "未知错误";
  const status = document.querySelector<HTMLElement>("#status");
  if (status !== null) {
    status.className = "fatal-status";
    status.textContent = `投影端初始化失败：${message}`;
  }
  console.error("projection.init_failed", error);
});
