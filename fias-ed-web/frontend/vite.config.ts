import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const shared = fileURLToPath(new URL("../../fias-ed-shared", import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@shared": shared } },
  server: { fs: { allow: [".", shared] }, proxy: { "/api": "http://127.0.0.1:8080" } },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    css: false,
    // Precisa ficar ACIMA do `asyncUtilTimeout` (10 s, ver src/test-setup.ts): se o
    // teste morresse antes, a falha viraria "test timed out" em vez de dizer qual
    // elemento não apareceu. O padrão de 5 s também já era apertado por si só — sob
    // carga o teste mais lento da suíte (fora o lint) chegou a 3889 ms medidos.
    testTimeout: 30_000,
  },
});
