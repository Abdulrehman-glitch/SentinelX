import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// GitHub Pages serves a project site under /<repo>/, so every asset URL needs
// that prefix. Root-hosted deployments (custom domain, local preview) keep "/".
// Set VITE_BASE_PATH=/SentinelX/ in the Pages build only — hard-coding it would
// break `npm run dev` and any root-hosted deployment.
const basePath = process.env.VITE_BASE_PATH ?? "/";

export default defineConfig({
  base: basePath,
  plugins: [react(), tailwindcss()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
  },
});