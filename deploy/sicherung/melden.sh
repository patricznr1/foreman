#!/usr/bin/env bash
# ============================================================
#  FOREMAN — deploy/sicherung/melden.sh
#  Zweck: Lebenszeichen und Alarm an healthchecks.io. Meldet den Erfolg der
#         täglichen Kette (Sicherung, dann außer Haus) und jeden
#         fehlgeschlagenen Job. Bleibt das Lebenszeichen aus, alarmiert der
#         Dienst selbst — auch dann, wenn der Server steht.
#  Architektur-Einordnung: Betrieb. Vorbild: deploy/sicherung/ im NEXUS-Repo.
# ============================================================
#
# Aufruf (root):
#   melden.sh ok                 Lebenszeichen (systemd: foreman-lebenszeichen.service,
#                                OnSuccess= von foreman-ausserhaus.service)
#   melden.sh fehler <unit>      Alarm (systemd: foreman-alarm@<unit>.service,
#                                OnFailure= der Jobs)
#
# Umgebung:
#   FOREMAN_PING_DATEI   Datei mit der Zeile FOREMAN_PING_URL=… (Vorgabe
#                        /srv/foreman/env/healthchecks.env, 600, nicht im Repository)
#
# NUR DER NAME DER UNIT geht hinaus, kein Protokoll: Das Journal der Jobs bleibt
# auf dem Server. Die URL wird gelesen, nicht ausgeführt, und nie ausgegeben.

set -euo pipefail

datei="${FOREMAN_PING_DATEI:-/srv/foreman/env/healthchecks.env}"
[ -r "$datei" ] || { echo "❌ $datei fehlt — deploy/README.md §5, Alarm einrichten" >&2; exit 1; }
url="$(sed -n 's/^FOREMAN_PING_URL=//p' "$datei" | tail -n 1)"
# Unter Windows geschriebene Datei: das CR gehörte sonst zur URL
url="${url%$'\r'}"
[[ "$url" == https://?* ]] || { echo "❌ $datei: FOREMAN_PING_URL fehlt oder ist kein https" >&2; exit 1; }
# Anführungszeichen, Backslash oder Leerraum zerbrächen die curl-Konfiguration unten
[[ "$url" != *[[:space:]\"\\]* ]] || { echo "❌ $datei: FOREMAN_PING_URL enthält unzulässige Zeichen" >&2; exit 1; }

# Die URL geht über stdin an curl (-K -), nicht in die Argumentliste: die steht
# für jeden Benutzer des Servers in /proc/<pid>/cmdline
ping_() {  # <url> [weitere curl-Optionen]
    local ziel="$1"
    shift
    printf 'url = "%s"\n' "$ziel" | curl -fsS -m 10 --retry 5 -o /dev/null -K - "$@"
}

case "${1:-}" in
    ok)
        ping_ "$url"
        echo "✅ Lebenszeichen gesendet"
        ;;
    fehler)
        unit="${2:-}"
        [[ "$unit" =~ ^[A-Za-z0-9@._-]+$ ]] || { echo "❌ Aufruf: melden.sh fehler <unit>" >&2; exit 2; }
        ping_ "$url/fail" --data-raw "$unit ist fehlgeschlagen — journalctl -u $unit"
        echo "🔥 Alarm gesendet: $unit"
        ;;
    *)
        echo "❌ Aufruf: melden.sh ok | fehler <unit>" >&2
        exit 2
        ;;
esac
