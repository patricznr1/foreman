# ============================================================
#  FOREMAN Frontend — Dockerfile
#  Zweck: schlankes Multi-Stage-Image für das Next.js-15-BFF-Frontend.
#         Build erzeugt das Standalone-Output (next.config: output="standalone"),
#         die Laufzeit startet nur den getracten Server — ohne dev-Toolchain.
#  Architektur-Einordnung: Betrieb (Schicht 0/1). Node-Version aus package.json
#         engines (>=20 <25) gepinnt; reproduzierbar via committetem package-lock.json.
# ============================================================

# Beide Stufen nennen dasselbe Image in der Form `tag@sha256:...` — dieselbe
# Festlegung wie im Backend-Dockerfile, wo die Begründung ausführlich steht: Der
# Tag sagt, WAS gemeint ist und wo eine Aktualisierung ansetzt; der Digest sagt,
# WELCHE Fassung. Ohne ihn baut derselbe Commit an zwei Tagen zwei Ergebnisse.
#
# Dazu ein Betriebsgrund: Eine bewegliche Marke muss bei JEDEM Bau erst bei der
# Registry aufgelöst werden (Tag → Digest). Ein Digest IST die Identität und kann
# aus dem Inhaltsspeicher des Builders bedient werden, ohne die Registry zu
# fragen. Das ist eine Abhängigkeit weniger, kein Freibrief: Liegt das Image
# nicht vor, braucht auch der Digest die Registry.
#
# Aktualisiert wird bewusst, nicht nebenbei; die Wiedervorlage führt
# security/findings.yaml unter F-009, wie beim Backend-Image.
# node:22-slim, OCI-Index mit linux/amd64 · arm · arm64 · ppc64le (28.08.2026).

# --- Stage 1: Build (Dev-Deps + Design-Tokens + next build) ---
FROM node:22-slim@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5 AS builder
WORKDIR /app

# Reproduzierbare Installation: NUR Manifest + committetes Lockfile zuerst (Layer-Cache).
# npm ci respektiert package-lock.json strikt (nie neu auflösen/regenerieren).
COPY package.json package-lock.json ./
RUN npm ci

# Quellbaum (nach .dockerignore gefiltert).
COPY . .

# NEXT_PUBLIC_* werden ZUR BUILD-ZEIT ins Browser-Bundle eingebacken — nicht zur Laufzeit.
# Die Live-WebSocket-URL muss daher schon hier stehen (öffentliche wss://…/api/v1/ws;
# Verdrahtung in DEPLOY.md). Railway reicht Service-Variablen als Build-Args durch;
# Default leer = die Übersicht bleibt auf dem HTTP-Erstbild (kein Live-Strom).
ARG NEXT_PUBLIC_FOREMAN_WS_URL=""
ENV NEXT_PUBLIC_FOREMAN_WS_URL=${NEXT_PUBLIC_FOREMAN_WS_URL}
ENV NEXT_TELEMETRY_DISABLED=1

# "build" = tokens:build (Design-Tokens → CSS) + next build (erzeugt .next/standalone).
RUN npm run build

# --- Stage 2: Runtime (nur Standalone-Server, kein npm/kein dev) ---
# Derselbe Digest wie die Baustufe — sonst liefe der Server auf einer anderen
# Fassung als der, gegen die gebaut wurde.
FROM node:22-slim@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5 AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
# Standalone-Server bindet an HOSTNAME/PORT; Railway injiziert PORT zur Laufzeit.
# 0.0.0.0: Railways Healthcheck-Prober (healthcheck.railway.app) erreicht den Server
# zuverlässig über IPv4 (Railway-Doku) — HOSTNAME=:: scheitert am Healthcheck
# ("service unavailable"). Das Frontend wird ohnehin nur öffentlich (Browser→Domain)
# angesprochen, kein eingehendes Private Networking nötig.
ENV HOSTNAME=0.0.0.0
ENV PORT=3000

# Unprivilegiert laufen (das offizielle node-Image bringt den Nutzer 'node' mit).
USER node

# Standalone-Bundle (server.js + minimale node_modules) und statische Assets
# übernehmen. public/ wird vom Next-Standalone-Output NICHT automatisch mitgenommen
# und muss explizit kopiert werden — sonst 404 auf alle public/-Assets (z. B. die
# Synoptik-GLBs und den Draco-Decoder).
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
COPY --from=builder --chown=node:node /app/public ./public

EXPOSE 3000

# Next-Standalone legt server.js ins Arbeitsverzeichnis.
CMD ["node", "server.js"]
