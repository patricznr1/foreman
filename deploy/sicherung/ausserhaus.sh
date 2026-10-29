#!/usr/bin/env bash
# ============================================================
#  FOREMAN — deploy/sicherung/ausserhaus.sh
#  Zweck: Sicherung außer Haus (restic -> Hetzner Storage Box). Lädt den
#         neuesten Lauf von sichern.sh und die Geheimnisse des Servers —
#         OHNE den Pseudonymisierungs-Schlüssel — verschlüsselt auf die Box,
#         hält die Aufbewahrung, prüft das Repository und holt beides zur
#         Probe zurück.
#  Architektur-Einordnung: Betrieb. Vorbild: deploy/sicherung/ im NEXUS-Repo.
# ============================================================
#
# Aufruf (root):
#   ausserhaus.sh einrichten   Passwortdatei und Repository anlegen (wiederholbar)
#   ausserhaus.sh sichern      neuesten Lauf hochladen, aufbewahren, prüfen
#                              (systemd: foreman-ausserhaus.service, OnSuccess= von
#                              foreman-sicherung.service)
#   ausserhaus.sh pruefen      neuesten Snapshot zurückholen und mit
#                              wiederherstellen.sh pruefen einspielen
#                              (systemd: foreman-ausserhaus-probe.timer, monatlich)
#
# Umgebung:
#   FOREMAN_SICHERUNG            Basisverzeichnis der Läufe wie sichern.sh
#   FOREMAN_GEHEIMNISSE          Verzeichnis der env-Dateien (Vorgabe /srv/foreman/env)
#   FOREMAN_AUSSERHAUS_REPO      restic-Repository (Vorgabe: Inhalt von
#                                /srv/foreman/env/restic.repo)
#   FOREMAN_AUSSERHAUS_PASSWORT  Passwortdatei (Vorgabe /srv/foreman/env/restic.passwort)
#   FOREMAN_AUSSERHAUS_TAEGLICH, _WOECHENTLICH, _MONATLICH  Aufbewahrung (14, 8, 6)
#
# DER PSEUDONYMISIERUNGS-SCHLÜSSEL BLEIBT DRAUSSEN (pseudo.env, Patric
# 29.10.2026): Löschen heißt bei FOREMAN, den Schlüssel einer Version zu
# vernichten (Crypto-Shredding, compliance/). Läge er in den Snapshots, lebte
# er dort bis zum Ende der Aufbewahrung weiter. Er liegt nur auf dem Server und
# in Patrics Passwortmanager. Die Passwortdatei bleibt ebenfalls draußen: Im
# Repository wäre sie ohne sich selbst unlesbar.
#
# WARUM --group-by host,tags: forget gruppiert sonst nach host,paths. Jeder
# Lauf liegt in einem eigenen Verzeichnis mit Zeitstempel, jede Gruppe hätte
# genau einen Snapshot, und die Aufbewahrung löschte nie etwas.
#
# DAS PASSWORT verlässt den Server nur durch Patric (Passwortmanager, README).
# einrichten gibt es nie aus.
#
# DIE ADRESSE DER BOX steht nur auf dem Server (restic.repo) und neben dem
# Passwort im Passwortmanager: Das Repository ist öffentlich, Konto und Name
# der Box gehören nicht hinein.

set -euo pipefail
shopt -s nullglob

hier="$(cd "$(dirname "$0")" && pwd)"
basis="${FOREMAN_SICHERUNG:-/srv/foreman/sicherung/taeglich}"
geheimnisse="${FOREMAN_GEHEIMNISSE:-/srv/foreman/env}"
for p in "$basis" "$geheimnisse"; do
    [[ "$p" == /?* ]] || { echo "❌ FOREMAN_SICHERUNG und FOREMAN_GEHEIMNISSE müssen absolute Pfade unterhalb von / sein: $p" >&2; exit 2; }
done
repo_datei="$geheimnisse/restic.repo"
if [ -z "${FOREMAN_AUSSERHAUS_REPO:-}" ]; then
    [ -s "$repo_datei" ] || { echo "❌ $repo_datei fehlt — deploy/README.md §5" >&2; exit 1; }
    FOREMAN_AUSSERHAUS_REPO="$(tr -d '\r\n' < "$repo_datei")"
fi
[[ "$FOREMAN_AUSSERHAUS_REPO" == sftp:?* ]] \
    || { echo "❌ restic-Repository muss mit sftp: beginnen (FOREMAN_AUSSERHAUS_REPO oder $repo_datei)" >&2; exit 2; }
export RESTIC_REPOSITORY="$FOREMAN_AUSSERHAUS_REPO"
export RESTIC_PASSWORD_FILE="${FOREMAN_AUSSERHAUS_PASSWORT:-/srv/foreman/env/restic.passwort}"
export RESTIC_CACHE_DIR="${RESTIC_CACHE_DIR:-/var/cache/foreman-ausserhaus}"
taeglich="${FOREMAN_AUSSERHAUS_TAEGLICH:-14}"
woechentlich="${FOREMAN_AUSSERHAUS_WOECHENTLICH:-8}"
monatlich="${FOREMAN_AUSSERHAUS_MONATLICH:-6}"
for n in "$taeglich" "$woechentlich" "$monatlich"; do
    [[ "$n" =~ ^[1-9][0-9]*$ ]] || { echo "❌ Aufbewahrung muss eine positive Zahl sein: $n" >&2; exit 2; }
done

# Fester Name statt hostname: Ein neu aufgesetzter Server setzt die Reihe fort
RECHNER=foreman-netcup
MARKE=foreman-taeglich
PSEUDO_DATEI="$geheimnisse/pseudo.env"
DATEIEN=(foreman.dump erweiterungen.txt SHA256SUMS)
MUSTER='[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9][0-9][0-9][0-9][0-9]Z'

command -v restic >/dev/null || { echo "❌ restic fehlt (apt install restic)" >&2; exit 2; }
[ -r "$hier/ssh_ausserhaus.conf" ] || { echo "❌ $hier/ssh_ausserhaus.conf fehlt" >&2; exit 2; }

# -F: nur die ssh-Konfiguration aus dem Repository, nichts von Hand Eingetragenes
restic_() { restic -o "sftp.args=-F $hier/ssh_ausserhaus.conf" --retry-lock 30m "$@"; }

passwort_da() {
    [ -s "$RESTIC_PASSWORD_FILE" ] \
        || { echo "❌ $RESTIC_PASSWORD_FILE fehlt — ausserhaus.sh einrichten, oder aus dem Passwortmanager zurückspielen" >&2; exit 1; }
}

einrichten() {
    if [ ! -e "$RESTIC_PASSWORD_FILE" ]; then
        (umask 077; head -c 48 /dev/urandom | base64 -w 0 > "$RESTIC_PASSWORD_FILE")
        echo "✅ Passwortdatei angelegt: $RESTIC_PASSWORD_FILE — jetzt in den Passwortmanager (deploy/README.md)"
    fi
    passwort_da
    # 0: Repository da, 10: keins (restic ab 0.17), sonst Netz, Schlüssel oder Passwort
    local rc=0
    restic_ cat config >/dev/null || rc=$?
    case "$rc" in
        0)  echo "📋 Repository besteht schon: $RESTIC_REPOSITORY" ;;
        10) restic_ init; echo "✅ Repository angelegt: $RESTIC_REPOSITORY" ;;
        *)  echo "❌ Repository nicht lesbar (restic Exit $rc) — nichts angelegt" >&2; exit 1 ;;
    esac
}

sichern() {
    passwort_da
    local laeufe=("$basis"/$MUSTER)
    [ "${#laeufe[@]}" -gt 0 ] || { echo "❌ keine Sicherung unter $basis" >&2; exit 1; }
    local lauf="${laeufe[-1]}"
    # Nur ein Lauf, dessen Prüfsummen stimmen, geht außer Haus
    (cd "$lauf" && sha256sum -c --quiet SHA256SUMS) \
        || { echo "❌ $lauf: Prüfsummen weichen ab — nicht hochgeladen" >&2; exit 1; }
    [ -d "$geheimnisse" ] || { echo "❌ $geheimnisse fehlt — nicht hochgeladen" >&2; exit 1; }
    echo "🔄 $lauf und $geheimnisse (ohne pseudo.env) -> $RESTIC_REPOSITORY"
    restic_ backup --host "$RECHNER" --tag "$MARKE" --group-by host,tags \
        --exclude "$RESTIC_PASSWORD_FILE" --exclude "$PSEUDO_DATEI" "$lauf" "$geheimnisse"
    echo "🔄 Aufbewahrung: $taeglich täglich, $woechentlich wöchentlich, $monatlich monatlich"
    restic_ forget --host "$RECHNER" --tag "$MARKE" --group-by host,tags \
        --keep-daily "$taeglich" --keep-weekly "$woechentlich" --keep-monthly "$monatlich" --prune
    restic_ check
    echo "✅ außer Haus: $(basename "$lauf")"
}

probe_aufraeumen() {
    local d f
    for d in "$probe$basis"/*/; do
        for f in "${DATEIEN[@]}"; do rm -f "$d$f"; done
        rmdir "$d" 2>/dev/null || true
    done
    # Geheimnisse: nur Dateien der obersten Ebene, wie sie gesichert wurden
    for f in "$probe$geheimnisse"/*; do
        if [ ! -d "$f" ]; then rm -f "$f"; fi
    done
    # Von innen nach außen; rmdir lässt alles stehen, was nicht leer ist
    for d in "$probe$basis" "$probe$geheimnisse"; do
        while [ "$d" != "$probe" ] && rmdir "$d" 2>/dev/null; do d="$(dirname "$d")"; done
    done
    rmdir "$probe" 2>/dev/null || echo "🔥 $probe enthält Fremdes — bleibt stehen" >&2
}

# Zurückgeholte Geheimnisse gegen den Server, ohne einen Wert auszugeben
geheimnisse_vergleichen() {
    local f n=0
    local -a anders=()
    for f in "$probe$geheimnisse"/*; do
        n=$((n + 1))
        cmp -s "$f" "$geheimnisse/$(basename "$f")" || anders+=("$(basename "$f")")
    done
    [ "$n" -gt 0 ] || { echo "❌ Snapshot ohne Geheimnisse unter $geheimnisse" >&2; exit 1; }
    [ ! -e "$probe$RESTIC_PASSWORD_FILE" ] || { echo "❌ Snapshot trägt die Passwortdatei" >&2; exit 1; }
    [ ! -e "$probe$PSEUDO_DATEI" ] || { echo "❌ Snapshot trägt den Pseudonymisierungs-Schlüssel" >&2; exit 1; }
    echo "📋 Geheimnisse: $n Dateien zurückgeholt, pseudo.env wie vorgesehen nicht dabei"
    # Nach einer Rotation weicht der Snapshot bis zum nächsten Lauf ab — Hinweis, kein Fehler
    [ "${#anders[@]}" -eq 0 ] || echo "🔥 seit dem Snapshot geändert oder neu: ${anders[*]}"
}

pruefen() {
    passwort_da
    probe="$(mktemp -d "$(dirname "$basis")/ausserhaus-probe.XXXXXX")"
    trap probe_aufraeumen EXIT
    echo "🔄 neuester Snapshot von $RESTIC_REPOSITORY -> $probe"
    restic_ restore latest --host "$RECHNER" --tag "$MARKE" --target "$probe"
    local laeufe=("$probe$basis"/$MUSTER)
    [ "${#laeufe[@]}" -eq 1 ] \
        || { echo "❌ Snapshot trägt ${#laeufe[@]} Läufe unter $basis, erwartet genau einen" >&2; exit 1; }
    geheimnisse_vergleichen
    bash "$hier/wiederherstellen.sh" pruefen "${laeufe[0]}"
    # Jeden Monat ein anderes Zwölftel der Daten: in einem Jahr alles einmal gelesen
    restic_ check --read-data-subset "$(date -u +%-m)/12"
    echo "✅ außer Haus wiederherstellbar: $(basename "${laeufe[0]}")"
}

case "${1:-}" in
    einrichten) einrichten ;;
    sichern)    sichern ;;
    pruefen)    pruefen ;;
    *) echo "❌ Aufruf: ausserhaus.sh einrichten | sichern | pruefen" >&2; exit 2 ;;
esac
