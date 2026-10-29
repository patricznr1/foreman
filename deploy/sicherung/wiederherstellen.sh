#!/usr/bin/env bash
# ============================================================
#  FOREMAN — deploy/sicherung/wiederherstellen.sh
#  Zweck: Sicherung prüfen oder wiederherstellen. pruefen spielt einen Lauf von
#         sichern.sh in eine Wegwerf-Datenbank ein und verwirft sie wieder;
#         einspielen spielt ihn in die leere Datenbank foreman ein.
#  Architektur-Einordnung: Betrieb. Vorbild: deploy/sicherung/ im NEXUS-Repo.
# ============================================================
#
# Aufruf (root oder Gruppe docker):
#   wiederherstellen.sh pruefen <lauf-verzeichnis | neueste>
#   wiederherstellen.sh einspielen <lauf-verzeichnis>
#
# systemd: foreman-sicherung-probe.timer führt `pruefen neueste` sonntags aus.
# Eine Sicherung, die nie eingespielt wurde, ist eine Annahme.
#
# einspielen leert nichts: Die Datenbank foreman muss leer sein
# (deploy/umzug/einspielen.sh prüft das). Sie zu leeren ist ein Schritt für
# einen Menschen (deploy/README.md §6). Backend und Worker müssen stehen.
#
# Umgebung: FOREMAN_COMPOSE, FOREMAN_SICHERUNG wie sichern.sh.

set -euo pipefail

hier="$(cd "$(dirname "$0")" && pwd)"
compose_text="${FOREMAN_COMPOSE:-docker compose -f $hier/../docker-compose.prod.yml}"
read -r -a compose <<< "$compose_text"
basis="${FOREMAN_SICHERUNG:-/srv/foreman/sicherung/taeglich}"
PROBE_DB="foreman_wiederherstellprobe"

modus="${1:-}"; lauf="${2:-}"
[[ "$modus" =~ ^(pruefen|einspielen)$ ]] && [ -n "$lauf" ] \
    || { echo "❌ Aufruf: wiederherstellen.sh pruefen <lauf|neueste> | einspielen <lauf>" >&2; exit 2; }
if [ "$lauf" = neueste ]; then
    [ "$modus" = pruefen ] || { echo "❌ einspielen braucht ein ausdrückliches Verzeichnis" >&2; exit 2; }
    shopt -s nullglob
    laeufe=("$basis"/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9][0-9][0-9][0-9][0-9]Z)
    [ "${#laeufe[@]}" -gt 0 ] || { echo "❌ keine Sicherung unter $basis" >&2; exit 1; }
    lauf="${laeufe[-1]}"
fi
[ -d "$lauf" ] || { echo "❌ $lauf ist kein Verzeichnis" >&2; exit 2; }

psql_su() { "${compose[@]}" exec -T timescaledb psql -X -v ON_ERROR_STOP=1 -U foreman -d postgres "$@"; }

# ── 1. Prüfsummen ────────────────────────────────────────────────────────────
echo "🔄 $lauf: Prüfsummen"
(cd "$lauf" && sha256sum -c --quiet SHA256SUMS) || { echo "❌ Prüfsummen weichen ab" >&2; exit 1; }

# ── 2a. Probe: Wegwerf-Datenbank, danach verworfen ───────────────────────────
if [ "$modus" = pruefen ]; then
    vorhanden="$(psql_su -Atc "select count(*) from pg_database where datname = '$PROBE_DB'")"
    [ "$vorhanden" = 0 ] || { echo "❌ $PROBE_DB gibt es schon — Rest eines früheren Laufs? Nicht angefasst" >&2; exit 1; }
    # Nur die Datenbank, die einspielen.sh gleich anlegt. with (force): Nach
    # post_restore laufen dort die Hintergrund-Jobs von TimescaleDB an.
    trap 'psql_su -q -c "drop database if exists $PROBE_DB with (force)" || echo "🔥 $PROBE_DB nicht verworfen" >&2' EXIT
    FOREMAN_PG_EXEC="$compose_text exec -T timescaledb" FOREMAN_DB="$PROBE_DB" \
        bash "$hier/../umzug/einspielen.sh" "$lauf/foreman.dump" "$lauf/erweiterungen.txt"
    echo "✅ $lauf lässt sich einspielen — $PROBE_DB wird verworfen"
    exit 0
fi

# ── 2b. Einspielen in die leere Datenbank foreman ────────────────────────────
FOREMAN_PG_EXEC="$compose_text exec -T timescaledb" \
    bash "$hier/../umzug/einspielen.sh" "$lauf/foreman.dump" "$lauf/erweiterungen.txt"
echo "✅ Datenbank aus $lauf wiederhergestellt — Start der Dienste: deploy/README.md §6"
