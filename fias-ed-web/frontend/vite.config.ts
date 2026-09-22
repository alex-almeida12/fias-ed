import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const shared = fileURLToPath(new URL("../../fias-ed-shared", import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@shared": shared } },
  server: { fs: { allow: [".", shared] }, proxy: { "/api": "http://127.0.0.1:8080" } },
  test: { environment: "jsdom", setupFiles: ["./src/test-setup.ts"], css: false },
});
