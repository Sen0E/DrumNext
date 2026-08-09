import { expect, test } from "@playwright/test";

test("renders the deterministic approach and hit scene", async ({ page }) => {
  await page.goto("/?timeMs=3700");
  const canvas = page.getByLabel("DrumNext WebGL2 场景");
  await expect(canvas).toBeVisible();
  await expect(canvas).toHaveScreenshot("dayu-layout-3700ms.png", {
    animations: "disabled",
    maxDiffPixelRatio: 0.01
  });
});

test("renders the spectacular ending style selected through the API", async ({ page, request }) => {
  const updated = await request.put("/api/v1/settings/ending-animation", {
    data: { style: "spectacular" }
  });
  expect(await updated.json()).toEqual({ style: "spectacular" });

  await page.goto("/?endingMs=3450");
  const canvas = page.getByLabel("DrumNext WebGL2 场景");
  await expect(canvas).toBeVisible();
  await expect(canvas).toHaveScreenshot("spectacular-ending-3450ms.png", {
    animations: "disabled",
    maxDiffPixelRatio: 0.01
  });

  await request.put("/api/v1/settings/ending-animation", {
    data: { style: "calm" }
  });
});

test("controls playback only through FastAPI", async ({ request }) => {
  const started = await request.post("/api/v1/playback/play");
  expect(started.ok()).toBe(true);
  expect((await started.json() as { status: string }).status).toBe("playing");

  const paused = await request.post("/api/v1/playback/pause");
  expect((await paused.json() as { status: string }).status).toBe("paused");
});

test("FastAPI hosts a working API debug interface", async ({ page }) => {
  await page.goto("http://127.0.0.1:18000/debug/api");
  await expect(page.getByRole("heading", { name: "DrumNext API 调试" })).toBeVisible();
  await page.getByRole("button", { name: "检查服务健康状态" }).click();
  await expect(page.locator("#output")).toContainText('"status": "ok"');
  await page.getByRole("button", { name: "播放", exact: true }).click();
  await expect(page.locator("#output")).toContainText('"status": "playing"');
  await page.getByRole("button", { name: "读取当前布局" }).click();
  await expect(page.getByLabel("布局 JSON")).toHaveValue(/"schemaVersion": 1/);
});

test("loads the score selected through FastAPI", async ({ page, request }) => {
  const selected = await request.post("/api/v1/playback/score", {
    data: { scoreId: "sparse-demo" }
  });
  expect((await selected.json() as { scoreId: string }).scoreId).toBe("sparse-demo");
  await page.goto("/?timeMs=1020");
  await expect(page.getByLabel("DrumNext WebGL2 场景")).toBeVisible();
  await request.post("/api/v1/playback/score", { data: { scoreId: "大鱼" } });
});

test("plays the calm ending animation once and restores the static drums", async ({ page, request }) => {
  await request.put("/api/v1/settings/ending-animation", { data: { style: "calm" } });
  await request.post("/api/v1/playback/score", { data: { scoreId: "sparse-demo" } });
  await request.post("/api/v1/playback/seek", { data: { positionMs: 4_000 } });
  await page.goto("/");
  const canvas = page.getByLabel("DrumNext WebGL2 场景");
  await expect(canvas).toBeVisible();
  await page.addStyleTag({ content: ".performance-panel { display: none !important; }" });
  const staticDrums = await canvas.screenshot({ animations: "disabled" });

  await request.post("/api/v1/playback/play");
  await request.post("/api/v1/playback/seek", { data: { positionMs: 4_000 } });
  await page.reload();
  await expect(canvas).toBeVisible();
  await page.addStyleTag({ content: ".performance-panel { display: none !important; }" });
  await page.waitForTimeout(650);
  const endingStarted = await canvas.screenshot({ animations: "disabled" });
  expect(endingStarted.equals(staticDrums)).toBe(false);

  await page.waitForTimeout(5_650);
  const restoredDrums = await canvas.screenshot({ animations: "disabled" });
  expect(restoredDrums.equals(staticDrums)).toBe(true);

  await request.post("/api/v1/playback/stop");
  await request.post("/api/v1/playback/score", { data: { scoreId: "大鱼" } });
});

test("sends snapshot before the scheduled note window", async ({ page }) => {
  await page.goto("/?timeMs=0");
  const messageTypes = await page.evaluate(async () => {
    const scheme = window.location.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(`${scheme}//${window.location.host}/ws/v1/projection`);
    return await new Promise<string[]>((resolve, reject) => {
      const types: string[] = [];
      const timer = window.setTimeout(() => reject(new Error("WebSocket timeout")), 3_000);
      socket.addEventListener("message", (event) => {
        const message = JSON.parse(String(event.data)) as { type: string };
        types.push(message.type);
        if (types.length === 2) {
          window.clearTimeout(timer);
          socket.close();
          resolve(types);
        }
      });
    });
  });
  expect(messageTypes).toEqual(["playback.snapshot", "notes.scheduled"]);
});
