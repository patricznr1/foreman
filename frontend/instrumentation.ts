// ============================================================
//  FOREMAN Frontend — instrumentation.ts
//  Zweck: Startprüfung des Servers. `register()` läuft einmal, bevor die erste
//         Anfrage bedient wird — hier bricht der Start ab, wenn die
//         Backend-Adresse im Betrieb fehlt. Ein geratener Wert würde sonst erst
//         beim ersten Anmeldeversuch auffallen, weit weg von seiner Ursache.
//  Architektur-Einordnung: Laufzeit-Startpunkt (Schicht 0). Läuft NICHT beim
//         Bauen: Next.js überspringt den Hook in `phase-production-build`.
// ============================================================
import { assertBackendUrlConfigured } from "@/lib/config/env";

export function register(): void {
  // Nur die Node.js-Laufzeit prüft — die Edge-Laufzeit bedient hier keine Route
  // und kennt `process.env` nur eingeschränkt.
  if (process.env.NEXT_RUNTIME !== "nodejs") {
    return;
  }
  assertBackendUrlConfigured();
}
