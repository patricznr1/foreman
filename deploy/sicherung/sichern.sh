#!/usr/bin/env bash
# ============================================================
#  FOREMAN — deploy/sicherung/sichern.sh
#  Zweck: Nächtliche Sicherung der TimescaleDB auf dem Server — pg_dump,
#         geprüft, mit Prüfsummen; behält die letzten N Läufe.
#  Architektur-Einordnung: Betrieb. Vorbild: deploy/sicherung/ im NEXUS-Repo.
# ============================================================
#
# Aufruf (root oder Gruppe docker; systemd: foreman-sicherung.timer, 03:15 UTC):
#   sichern.sh
#
# Ziel: ${FOREMAN_SICHERUNG:-/srv/foreman/sicherung/taeglich}/<UTC-Zeitstempel>/
#   foreman.dump       pg_dump -Fc der Datenbank foreman (wiederherstellen.sh)
#   erweiterungen.txt  Fassungen von timescaledb und timescaledb_toolkit — das
#                      Einspielen legt genau diese an (deploy/umzug/einspielen.sh)
#   SHA256SUMS         sha256sum -c im Verzeichnis
#
# Umgebung:
#   FOREMAN_COMPOSE             Compose-Aufruf (Vorgabe: die Compose-Datei daneben)
#   FOREMAN_SICHERUNG           Basisverzeichnis
#   FOREMAN_SICHERUNG_BEHALTEN  Zahl der Läufe, die bleiben (Vorgabe 14)
#
# Die Messwerte von readings liegen in den Chunks der Hypertable, nicht in der
# Tabelle selbst — die Prüfung des Inhaltsverzeichnisses sucht deshalb auch
# nach Chunk-Daten unter _timescaledb_internal.
#
# Die Sicherung entsteht erst unter <stempel>.teil und wird nur nach allen
# Prüfungen umbenannt; scheitert ein Schritt, räumt der Lauf seine eigenen
# Dateien weg und endet mit 1. Die Rotation löscht nur bekannte Dateien.

set -euo pipefail

hier="$(cd "$(dirname "$0")" && pwd)"
read -r -a compose <<< "${FOREMAN_COMPOSE:-docker compose -f $hier/../docker-compose.prod.yml}"
basis="${FOREMAN_SICHERUNG:-/srv/foreman/sicherung/taeglich}"
# Die Rotation löscht unter $basis — nur unter einem absoluten Pfad unterhalb von /
[[ "$basis" == /?* ]] || { echo "❌ FOREMAN_SICHERUNG muss ein absoluter Pfad unterhalb von / sein: $basis" >&2; exit 2; }
behalten="${FOREMAN_SICHERUNG_BEHALTEN:-14}"
[[ "$behalten" =~ ^[1-9][0-9]*$ ]] || { echo "❌ FOREMAN_SICHERUNG_BEHALTEN muss eine positive Zahl sein: $behalten" >&2; exit 2; }

DATEIEN=(foreman.dump erweiterungen.txt SHA256SUMS)
stempel="$(date -u +%Y-%m-%dT%H%M%SZ)"
ziel="$basis/$stempel"
teil="$ziel.teil"
for p in "$ziel" "$teil"; do
    [ ! -e "$p" ] || { echo "❌ $p gibt es schon — nichts überschrieben" >&2; exit 2; }
done

umask 077
mkdir -p "$basis"
mkdir "$teil"
fertig=0
aufraeumen() {
    [ "$fertig" = 1 ] && return
    for f in "${DATEIEN[@]}"; do rm -f "$teil/$f"; done
    rmdir "$teil" 2>/dev/null || echo "🔥 $teil enthält fremde Dateien — bleibt stehen" >&2
}
trap aufraeumen EXIT

psql_() { "${compose[@]}" exec -T timescaledb psql -X -v ON_ERROR_STOP=1 -U foreman -d foreman "$@"; }

# ── 1. Datenbank ─────────────────────────────────────────────────────────────
echo "🔄 pg_dump der Datenbank foreman"
"${compose[@]}" exec -T timescaledb pg_dump -U foreman -d foreman -Fc -Z6 > "$teil/foreman.dump"
psql_ -At -F ' ' -c "select extname, extversion from pg_extension where extname in ('timescaledb', 'timescaledb_toolkit') order by 1" \
    > "$teil/erweiterungen.txt"
[ "$(wc -l < "$teil/erweiterungen.txt")" = 2 ] || { echo "❌ timescaledb oder timescaledb_toolkit fehlt in foreman" >&2; exit 1; }

# ── 2. Inhaltsverzeichnis: lesbar, mit den Daten der Kerntabellen ────────────
inhalt="$("${compose[@]}" exec -T timescaledb pg_restore --list < "$teil/foreman.dump")"
for tabelle in alembic_version machines semantic_events worker_notes users; do
    grep -q " TABLE DATA public $tabelle " <<< "$inhalt" \
        || { echo "❌ Sicherung ohne Daten von $tabelle — Inhaltsverzeichnis unvollständig" >&2; exit 1; }
done
grep -q " TABLE DATA _timescaledb_internal _hyper_" <<< "$inhalt" \
    || { echo "❌ Sicherung ohne Chunk-Daten der Hypertables" >&2; exit 1; }

# ── 3. Prüfsummen, Abschluss ─────────────────────────────────────────────────
(cd "$teil" && sha256sum foreman.dump erweiterungen.txt) > "$teil/SHA256SUMS"
mv "$teil" "$ziel"
fertig=1
echo "✅ gesichert in $ziel: foreman.dump $(stat -c %s "$ziel/foreman.dump") Bytes"

# ── 4. Rotation: die ältesten Läufe über der Grenze ──────────────────────────
shopt -s nullglob
laeufe=("$basis"/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9][0-9][0-9][0-9][0-9]Z)
rotation_ok=1
for ((i = 0; i < ${#laeufe[@]} - behalten; i++)); do
    alt="${laeufe[$i]}"
    for f in "${DATEIEN[@]}"; do rm -f "$alt/$f"; done
    if rmdir "$alt" 2>/dev/null; then
        echo "📋 entfernt: $alt"
    else
        echo "🔥 $alt enthält fremde Dateien — bleibt stehen" >&2
        rotation_ok=0
    fi
done
[ "$rotation_ok" = 1 ] || { echo "❌ Sicherung vollständig, Rotation unvollständig" >&2; exit 1; }
