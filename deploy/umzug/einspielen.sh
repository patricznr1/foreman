#!/usr/bin/env bash
# ============================================================
#  FOREMAN — deploy/umzug/einspielen.sh
#  Zweck: Eine Sicherung (pg_dump -Fc) in eine frische Datenbank einspielen,
#         auf dem Weg, den TimescaleDB für Hypertables vorschreibt.
#  Architektur-Einordnung: Betrieb. Aufrufer: der Umzug von Railway und
#         deploy/sicherung/wiederherstellen.sh.
# ============================================================
#
# Aufruf:
#   einspielen.sh <foreman.dump> <erweiterungen.txt>
#
# erweiterungen.txt nennt je Zeile `<name> <fassung>` für timescaledb und
# timescaledb_toolkit — sichern.sh schreibt sie neben den Dump.
#
# DER WEG (TimescaleDB-Doku, „Logical backups"):
#   1. Datenbank aus template0, damit keine Erweiterung vorher da ist
#   2. timescaledb und timescaledb_toolkit in GENAU der Fassung der Sicherung —
#      das Abbild brächte von sich aus eine neuere mit, und die Kataloge der
#      Sicherung passen nur zu ihrer eigenen
#   3. timescaledb_pre_restore() → pg_restore → timescaledb_post_restore()
# Geprobt am 29.10.2026 mit dem Dump von Railway (deploy/README.md §4).
#
# WARUM DIE DATENBANK HIER NEU ENTSTEHT: Das Init-Skript des Abbilds legt in
# POSTGRES_DB beim ersten Start timescaledb in seiner eigenen Fassung an. Eine
# vorhandene Zieldatenbank wird deshalb verworfen und neu angelegt — aber nur,
# wenn in public nichts liegt. Eine Datenbank mit Inhalt fasst das Skript
# nicht an.
#
# Umgebung:
#   FOREMAN_PG_EXEC  Befehl, der im Datenbank-Container ausführt
#   FOREMAN_DB       Zieldatenbank (Vorgabe: foreman)

set -euo pipefail

hier="$(cd "$(dirname "$0")" && pwd)"
dump="${1:-}"
erweiterungen="${2:-}"
[ -n "$dump" ] && [ -r "$dump" ] || { echo "❌ Sicherung fehlt oder ist nicht lesbar: ${dump:-<leer>}" >&2; exit 2; }
[ -n "$erweiterungen" ] && [ -r "$erweiterungen" ] \
    || { echo "❌ erweiterungen.txt fehlt oder ist nicht lesbar: ${erweiterungen:-<leer>}" >&2; exit 2; }

read -r -a pg_exec <<< "${FOREMAN_PG_EXEC:-docker compose -f $hier/../docker-compose.prod.yml exec -T timescaledb}"
db="${FOREMAN_DB:-foreman}"
[[ "$db" =~ ^[a-z_][a-z0-9_]*$ ]] || { echo "❌ FOREMAN_DB nur aus a-z, 0-9 und _: $db" >&2; exit 2; }

psql_in() { local ziel="$1"; shift; "${pg_exec[@]}" psql -X -v ON_ERROR_STOP=1 -U foreman -d "$ziel" "$@"; }

# ── 0. Fassungen aus der Sicherung ───────────────────────────────────────────
mapfile -t zeilen < <(tr -d '\r' < "$erweiterungen")
[ "${#zeilen[@]}" = 2 ] && [[ "${zeilen[0]}" =~ ^timescaledb\ [0-9.]+$ ]] && [[ "${zeilen[1]}" =~ ^timescaledb_toolkit\ [0-9.]+$ ]] \
    || { echo "❌ $erweiterungen: erwartet 'timescaledb <fassung>' und 'timescaledb_toolkit <fassung>'" >&2; exit 1; }
echo "📋 Fassungen der Sicherung: ${zeilen[0]}, ${zeilen[1]}"

# ── 1. Frische Datenbank ─────────────────────────────────────────────────────
vorhanden="$(psql_in postgres -Atc "select count(*) from pg_database where datname = '$db'")"
if [ "$vorhanden" = 1 ]; then
    objekte="$(psql_in "$db" -Atc "select count(*) from pg_class c join pg_namespace n on n.oid = c.relnamespace where n.nspname = 'public'")"
    [ "$objekte" = 0 ] || { echo "❌ $db ist nicht leer ($objekte Objekte in public) — nichts eingespielt" >&2; exit 1; }
    echo "🔄 $db ist leer und wird aus template0 neu angelegt"
    psql_in postgres -q -c "drop database $db"
fi
psql_in postgres -q -c "create database $db template template0"

# ── 2. Erweiterungen in der Fassung der Sicherung ────────────────────────────
for zeile in "${zeilen[@]}"; do
    read -r name fassung <<< "$zeile"
    psql_in "$db" -q -c "create extension $name version '$fassung'"
done

# ── 3. Einspielen ────────────────────────────────────────────────────────────
echo "🔄 Sicherung nach $db einspielen ($(date -u +%H:%M:%SZ))"
psql_in "$db" -qAtc "select timescaledb_pre_restore()" > /dev/null
if ! "${pg_exec[@]}" pg_restore -U foreman -d "$db" --no-owner --exit-on-error < "$dump"; then
    echo "❌ pg_restore abgebrochen — $db ist halb eingespielt und steht im Wiederherstellungsmodus." >&2
    echo "   Verwerfen ist ein Schritt für einen Menschen: drop database $db (deploy/README.md §6)" >&2
    exit 1
fi
psql_in "$db" -qAtc "select timescaledb_post_restore()" > /dev/null
psql_in "$db" -q -c "analyze"
echo "📋 fertig ($(date -u +%H:%M:%SZ))"

# ── 4. Nachprüfung ───────────────────────────────────────────────────────────
nachher="$(psql_in "$db" -At -F ' ' -c "select extname, extversion from pg_extension where extname in ('timescaledb', 'timescaledb_toolkit') order by 1")"
[ "$nachher" = "$(printf '%s\n%s' "${zeilen[0]}" "${zeilen[1]}")" ] \
    || { echo "❌ Fassungen nach dem Einspielen weichen ab: $nachher" >&2; exit 1; }
echo "📋 Alembic-Stand $(psql_in "$db" -Atc "select version_num from alembic_version")"
echo "📋 Zeilen je Tabelle:"
psql_in "$db" -At -F ' ' <<'SQL'
select table_name,
       (xpath('/row/c/text()', query_to_xml(format('select count(*) as c from public.%I', table_name), false, true, '')))[1]::text
  from information_schema.tables
 where table_schema = 'public' and table_type in ('BASE TABLE', 'VIEW')
 order by 1;
SQL
echo "✅ Sicherung nach $db eingespielt"
