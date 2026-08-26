// ============================================================
//  FOREMAN Frontend — next.config.ts
//  Zweck: Next.js-App-Konfiguration. Die Backend-Anbindung läuft NICHT über
//         next.config-Rewrites, sondern über einen BFF-Route-Handler-Proxy
//         (app/api/v1/[...path]), der das httpOnly-Cookie-Token als Bearer
//         injiziert — so bleibt das JWT vor Browser-JS geschützt und das
//         Backend braucht keine CORS-Lockerung (chirurgisch, kein Backend-Change).
//  Sicherheits-Kopfzeilen: siehe `sicherheitsKopfzeilen` unten — sie gelten für
//         JEDE ausgelieferte Antwort, damit keine Route sie versehentlich verliert.
//  Architektur-Einordnung: Build-/Runtime-Konfiguration (Schicht 0).
// ============================================================
import type { NextConfig } from "next";

const istEntwicklung = process.env.NODE_ENV === "development";

/**
 * Der Ursprung, zu dem der Live-Strom verbindet.
 *
 * Der Browser spricht den WebSocket des Backends DIREKT an — nicht über den
 * BFF-Proxy, der kein Upgrade weiterreicht. Die Regel `connect-src` muss diesen
 * Ursprung deshalb ausdrücklich führen, sonst bricht der Live-Strom, sobald die
 * Richtlinie greift. Ohne gesetzte Variable bleibt es beim gleichen Ursprung,
 * und `'self'` deckt ihn ab.
 */
function liveStromUrsprung(): string {
  const rohwert = process.env.NEXT_PUBLIC_FOREMAN_WS_URL;
  if (!rohwert) {
    return "";
  }
  try {
    return new URL(rohwert).origin;
  } catch {
    // Eine unlesbare Angabe wird NICHT stillschweigend in die Richtlinie
    // übernommen — sonst stünde dort ein Wert, den niemand geprüft hat.
    return "";
  }
}

/**
 * Die Inhaltsrichtlinie (Content-Security-Policy).
 *
 * WAS SIE DECKT: fremde Skript- und Stilquellen, das Einbetten der Anwendung in
 * einen fremden Rahmen (`frame-ancestors 'none'`), eingebettete Objekte, die
 * Manipulation der Basis-Adresse und fremde Formularziele.
 *
 * WAS SIE NICHT DECKT — und das steht hier, damit niemand mehr hineinliest, als
 * drinsteht: `script-src` führt `'unsafe-inline'`. Gegen eingeschleusten
 * Inline-Code schützt diese Richtlinie also nicht. Der saubere Weg wäre eine
 * Einmal-Kennung (Nonce) je Anfrage; die verlangt bei Next.js, dass JEDE Seite
 * dynamisch gerendert wird, weil die Kennung aus den Kopfzeilen der Anfrage
 * stammt. Diese Anwendung liefert Seiten statisch vorgerendert aus — der Umstieg
 * ist eine Architekturentscheidung mit Kosten bei der Auslieferung und gehört
 * nicht nebenbei erledigt. Bis dahin gilt: eine Richtlinie, die den größeren Teil
 * der Angriffsfläche schließt, ist besser als keine, aber sie ersetzt die
 * Ausgabe-Maskierung im Code nicht.
 *
 * `'wasm-unsafe-eval'` ist für den mitgelieferten Draco-Dekoder nötig, der die
 * 3D-Geometrie der Synoptik entpackt. Ohne ihn bleibt die Anlagenansicht leer.
 */
function inhaltsRichtlinie(): string {
  const ws = liveStromUrsprung();
  const verbindungsziele = ["'self'", ws].filter(Boolean).join(" ");
  const regeln = [
    "default-src 'self'",
    // In der Entwicklung braucht der Neuladen-Mechanismus `'unsafe-eval'`;
    // im Betrieb ist er ausdrücklich nicht dabei.
    `script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'${istEntwicklung ? " 'unsafe-eval'" : ""}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    `connect-src ${verbindungsziele}`,
    "worker-src 'self' blob:",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "upgrade-insecure-requests",
  ];
  return regeln.join("; ");
}

/**
 * Kopfzeilen, die jede Antwort trägt.
 *
 * Bewusst hier und nicht je Route: Eine Kopfzeile, die man je Route setzen muss,
 * fehlt früher oder später an genau der Route, an der sie zählt.
 */
const sicherheitsKopfzeilen = [
  {
    key: "Content-Security-Policy",
    value: inhaltsRichtlinie(),
  },
  {
    // Zwei Jahre, Unterdomänen eingeschlossen. Der Browser spricht die Anwendung
    // danach nur noch verschlüsselt an — ein abgefangener erster Aufruf über
    // Klartext entfällt damit ab dem zweiten Besuch.
    key: "Strict-Transport-Security",
    value: "max-age=63072000; includeSubDomains; preload",
  },
  {
    // Deckungsgleich mit `frame-ancestors 'none'` oben. Bewusst doppelt: Ältere
    // Browser kennen die Richtlinien-Fassung nicht, verstehen aber diese Zeile.
    key: "X-Frame-Options",
    value: "DENY",
  },
  {
    // Der Browser hält sich an den angegebenen Inhaltstyp, statt ihn zu raten —
    // sonst wird aus einer hochgeladenen Textdatei unter Umständen Skriptcode.
    key: "X-Content-Type-Options",
    value: "nosniff",
  },
  {
    // Beim Wechsel auf eine fremde Seite reist nur der Ursprung mit, nicht der
    // vollständige Pfad. Pfade dieser Anwendung tragen Maschinen- und
    // Datensatz-Kennungen; die gehen fremde Server nichts an.
    key: "Referrer-Policy",
    value: "strict-origin-when-cross-origin",
  },
  {
    // Die Anwendung braucht weder Kamera noch Mikrofon noch Standort. Was nicht
    // gebraucht wird, wird abgeschaltet — auch für eingebettete Inhalte.
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), interest-cohort=()",
  },
];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Schlankes Container-Image: Next bündelt den getracten Server (+ minimale
  // node_modules) nach .next/standalone — die Laufzeit braucht keine dev-Toolchain
  // und kein npm install mehr (Dockerfile übernimmt nur standalone + .next/static).
  output: "standalone",
  // Kein `X-Powered-By`. Die Kopfzeile nennt das eingesetzte Rahmenwerk und
  // erspart einem Angreifer den ersten Schritt: herauszufinden, wogegen er sucht.
  poweredByHeader: false,
  // Lint ist ein eigenes Quality-Gate (npm run lint) — nicht im Build doppeln.
  eslint: { ignoreDuringBuilds: true },
  experimental: {
    // Erstbild schlank halten (Studie 1.2: < 100 KB kritischer Pfad).
    optimizePackageImports: [],
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: sicherheitsKopfzeilen,
      },
    ];
  },
};

export default nextConfig;
