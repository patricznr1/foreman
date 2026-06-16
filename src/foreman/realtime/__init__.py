# ============================================================
#  FOREMAN — realtime/__init__.py
#  Zweck: Der Live-Push-Layer (F5). Producer-Seite (notify): ein dünnes
#         pg_notify pro Commit/Batch. Consumer-Seite (hub/ws): eine LISTEN-
#         Verbindung + Themen-Hub PRO Worker, der per debounce→load über den
#         Read-Core nachlädt und an die WebSocket-Abonnenten verteilt. Transport
#         ist Postgres LISTEN/NOTIFY (Stack ohne Redis/Celery) — entkoppelt den
#         separaten Ingest-Prozess von der API, Postgres-nativ.
#  Architektur-Einordnung: Schnittstellen-/Transport-Schicht über dem Read-Core.
#  Invariante: read-only nach außen — der Push trägt Zustand, keine Aktorik.
# ============================================================
from __future__ import annotations
