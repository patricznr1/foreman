// ============================================================
//  FOREMAN Frontend — vitest.config.ts
//  Zweck: Test-Runner für Tokens, Echtzeit-/State-Schicht, Atome, Shell,
//         Rollen-Routing und den vertikalen Durchstich. jsdom + Testing Library.
//  Architektur-Einordnung: Quality-Gate (npm test, §10.3). Transport-agnostisch:
//         Komponenten werden gegen Fake-Transport/Cache UND Stream getestet.
// ============================================================
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    globals: false,
    setupFiles: ["./vitest.setup.ts"],
    include: ["**/*.{test,spec}.{ts,tsx}"],
    exclude: ["node_modules/**", ".next/**", "e2e/**"],
    css: false,
    clearMocks: true,
  },
});
