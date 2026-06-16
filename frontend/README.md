# FOREMAN Frontend

Der Werker-Output-Kanal von FOREMAN — eine ruhige, rollenbasierte Hallen-Oberfläche.
**Verbindliche Designgrundlage:** [`../docs/research/FOREMAN_Designstudie_Frontend.md`](../docs/research/FOREMAN_Designstudie_Frontend.md). Verträge: [`../GROUND_TRUTH.md`](../GROUND_TRUTH.md) §21.

Stack: Next.js 15 (App Router) · React 19 · TypeScript strict · Tailwind CSS 4 · Vitest.

## Entwicklung

```bash
npm install
npm run tokens:build   # Design-Tokens → app/styles/tokens.generated.css
npm run dev            # http://localhost:3000
```

Das Frontend spricht das Backend nicht direkt, sondern über einen **BFF-Proxy**
(Route-Handler injizieren das JWT aus einem httpOnly-Cookie als Bearer) — das
Backend braucht keine CORS-Lockerung.

### Umgebungsvariablen

| Variable | Zweck | Default |
|---|---|---|
| `FOREMAN_API_URL` | Backend-Basis (server-seitig) | `http://localhost:8000` |
| `NEXT_PUBLIC_FOREMAN_WS_URL` | Live-WebSocket (client-seitig) | `ws://localhost:8000/api/v1/ws` empfohlen |

Ohne gesetztes `NEXT_PUBLIC_FOREMAN_WS_URL` zeigt die Übersicht das HTTP-Erstbild
(als „gecacht"); Live-Updates kommen erst mit konfiguriertem WebSocket.

## Quality-Gates

```bash
npm run typecheck    # tsc --noEmit (strict)
npm run lint         # ESLint
npm test             # Vitest (Tokens, Echtzeit-Schicht, Atome, Shell, Durchstich)
npm run build        # Production-Build
npm run tokens:check # CI: generierte Token-CSS == Quelle
```

## Architektur (Kurz)

- **Token-Quelle** `tokens/` → drei Ebenen (primitive → semantic → theme dark/hc-light),
  Generator nach `app/styles/tokens.generated.css`. Kontrast automatisiert geprüft.
- **Echtzeit-/State-Schicht** `lib/realtime/` + `lib/state/` — strikte Transport-
  Entkopplung (Studie §5.1): `Transport`-Interface, `WebSocketTransport`, `RealtimeStore`
  (gepuffert/gedrosselt), abgeleitete View-State-Ebene mit fünf Pflichtzuständen.
  Visualisierung kennt den Transport nie (transport-agnostisch getestet).
- **BFF & Auth** `lib/auth/` + `app/api/` — httpOnly-Cookie-JWT, Proxy, WS-Ticket,
  Rolle/Scope aus `GET /api/v1/me`. Rollenmatrix 3.1; Sichtbarkeit ≤ Server-Autorisierung.
- **Atome & Shell** `components/` — StatusIndicator, ProvenanceStamp, KpiTile,
  Fünf-Zustände-Hülle; GlobalStatusBar (live), Breadcrumb, Befehlsleiste (⌘K),
  Schnellerfassung, rollengefilterte Navigation.
- **Durchstich** `views/overview/` — Flotten-Übersicht: HTTP-Snapshot + WS-Live.

## Drei bleibende Haltungen (Verfassung, kein Feature)

1. **Simulations-Vorbehalt** an jeder Ausfallvorhersage sichtbar (greift voll in Sektion E).
2. **Human-in-the-Loop ohne Aktorik** — die Plattform erklärt und empfiehlt, schaltet nie.
3. **Gedächtnis nach außen paraphrasiert** — kein internes Vokabular im sichtbaren Wording.

## Bewusst verschoben (eigene Prompts)

Die zehn Sektionen (C/E zuerst), WebGL (A/G), Sprach-UI (J), Electron,
Service-Worker-Vollausbau, Playwright-E2E, Font-Selfhosting.
