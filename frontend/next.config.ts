// ============================================================
//  FOREMAN Frontend — next.config.ts
//  Zweck: Next.js-App-Konfiguration. Die Backend-Anbindung läuft NICHT über
//         next.config-Rewrites, sondern über einen BFF-Route-Handler-Proxy
//         (app/api/v1/[...path]), der das httpOnly-Cookie-Token als Bearer
//         injiziert — so bleibt das JWT vor Browser-JS geschützt und das
//         Backend braucht keine CORS-Lockerung (chirurgisch, kein Backend-Change).
//  Architektur-Einordnung: Build-/Runtime-Konfiguration (Schicht 0).
// ============================================================
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Lint ist ein eigenes Quality-Gate (npm run lint) — nicht im Build doppeln.
  eslint: { ignoreDuringBuilds: true },
  experimental: {
    // Erstbild schlank halten (Studie 1.2: < 100 KB kritischer Pfad).
    optimizePackageImports: [],
  },
};

export default nextConfig;
