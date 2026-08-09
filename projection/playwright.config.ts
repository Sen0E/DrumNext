import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  outputDir: "../test-results",
  snapshotDir: "./snapshots",
  use: {
    baseURL: "http://127.0.0.1:4173",
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1
  },
  webServer: [
    {
      command: "DRUMNEXT_ENDING_ANIMATION_FILE=/tmp/drumnext-e2e-ending-animation.json uv run uvicorn drumnext.main:app --host 127.0.0.1 --port 18000",
      cwd: fileURLToPath(new URL("..", import.meta.url)),
      url: "http://127.0.0.1:18000/api/v1/health",
      reuseExistingServer: false
    },
    {
      command: "DRUMNEXT_BACKEND_URL=http://127.0.0.1:18000 npm run build && DRUMNEXT_BACKEND_URL=http://127.0.0.1:18000 npm exec vite preview -- --config projection/vite.config.ts --host 127.0.0.1 --port 4173",
      cwd: fileURLToPath(new URL("..", import.meta.url)),
      url: "http://127.0.0.1:4173",
      reuseExistingServer: false
    }
  ]
});
