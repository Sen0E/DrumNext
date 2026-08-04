import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";

const backendUrl = process.env.DRUMNEXT_BACKEND_URL ?? "http://127.0.0.1:8000";
const proxy = {
  "/api": backendUrl,
  "/ws": { target: backendUrl, ws: true }
};

export default defineConfig({
  root: fileURLToPath(new URL(".", import.meta.url)),
  build: {
    outDir: fileURLToPath(new URL("../dist", import.meta.url)),
    emptyOutDir: true,
    target: "es2022"
  },
  server: {
    host: "0.0.0.0",
    proxy
  },
  preview: { proxy }
});
