# ============================================================
#  FOREMAN — deploy/server/geheimnisse.py
#  Zweck: Geheimnisdateien unter /srv/foreman/env anlegen und von Railway
#         übernehmen, ohne je einen Wert auszugeben.
#  Architektur-Einordnung: Betrieb. Nur Standardbibliothek — läuft mit dem
#         python3 des Servers, ohne die Abhängigkeiten der App.
# ============================================================
"""Geheimnisdateien für deploy/docker-compose.prod.yml.

anlegen
    Erzeugt die Zugänge, die es nur auf dem Server gibt: das Passwort der
    Datenbank (timescaledb.env) und die Adresse, die es trägt (zugang.env).
    Beide oder keine, und nur einmal: POSTGRES_PASSWORD wirkt nur beim ersten
    Start der Datenbank.

uebernehmen <dienst>
    Liest ``railway variables --json`` des Railway-Dienstes von stdin. Jeder Name
    muss eingeordnet sein — ein unbekannter bricht ab, statt still zu fehlen:
      - ``FOREMAN_PSEUDO_KEY_v<N>`` gehen nach pseudo.env. Backend und Worker
        teilen sie; der zweite Dienst vergleicht nur.
      - Die Namen der Liste des Dienstes gehen wörtlich nach <dienst>.env —
        Geheimnisse wie Schalter, deren Werte hier niemand liest.
      - Was auf dem Server anders entsteht, wird genannt und übergangen.
    Gibt es eine Datei schon, wird verglichen, nie überschrieben. So ist ein
    zweiter Lauf beim Umschalten die Prüfung gegen den Live-Stand.

Warum eine Positivliste: Compose liest die Geheimnisdatei NACH der
Konfiguration, und bei gleichem Namen gewinnt die spätere Datei. Die Listen
sind disjunkt zu deploy/konfig (tests/unit/test_deploy_geheimnisse.py) — so
kann eine Geheimnisdatei keine Server-Einstellung verstellen.

Werte stehen einfach quotiert (Compose nimmt sie dann wörtlich, auch $ und #);
ein Wert mit ', Zeilenumbruch oder abschließendem Backslash wird abgelehnt.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO

KONFIG_VERZEICHNIS = Path(__file__).resolve().parents[1] / "konfig"
ENV_VERZEICHNIS = Path("/srv/foreman/env")
PASSWORT_BYTES = 32
EINGABE_GRENZE = 1024 * 1024

# Kleinbuchstaben kommen vor: FOREMAN_PSEUDO_KEY_v1 (config.py, Schlüsselversion)
NAME_MUSTER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
PSEUDO_MUSTER = re.compile(r"^FOREMAN_PSEUDO_KEY_v[0-9]+$")
PSEUDO_DATEI = "pseudo.env"

# Setzen Railway oder das Abbild selbst; auf dem Server tun das Compose und das Abbild
NIE_UEBERNEHMEN = frozenset(
    {"HF_HOME", "HOME", "HOSTNAME", "LANG", "PATH", "PORT", "PWD", "PYTHONPATH", "TERM"}
)
RAILWAY_PRAEFIX = "RAILWAY_"

# Müssen zu deploy/docker-compose.prod.yml passen (POSTGRES_USER, POSTGRES_DB, Dienstname)
PG_ROLLE = "foreman"
PG_DATENBANK = "foreman"
PG_HOST = "timescaledb:5432"

# Gemeinsam: die fünf Pfade der Substrat-Fassade und der Mandanten-Schlüssel
_SUBSTRAT = frozenset(
    {
        "SUBSTRATE_DRIFT_STATUS_PATH",
        "SUBSTRATE_FORGET_PATH",
        "SUBSTRATE_REASON_PATH",
        "SUBSTRATE_RECALL_PATH",
        "SUBSTRATE_REFLECT_PATH",
        "SUBSTRATE_REMEMBER_PATH",
        "SUBSTRATE_TOKEN",
    }
)
_PSEUDO_SCHALTER = frozenset(
    {"FOREMAN_PSEUDO_KEY_VERSION", "FOREMAN_PSEUDO_KEY_VERSIONS", "FOREMAN_PSEUDO_TENANT"}
)
_SERVER_ANDERS = {
    "DATABASE_URL": "entsteht mit anlegen (zugang.env)",
    "SUBSTRATE_BASE_URL": "auf dem Server in deploy/konfig (gemeinsame NEXUS-Instanz)",
}


class BefundError(Exception):
    """Ein Befund, der das Schreiben verhindert. Die Meldung trägt nie einen Wert."""


@dataclass(frozen=True)
class Dienst:
    konfig: str
    railway_quelle: str
    uebernehmen: frozenset[str]
    nicht_uebernommen: dict[str, str] = field(default_factory=dict)


DIENSTE: dict[str, Dienst] = {
    "backend": Dienst(
        konfig="backend.conf.env",
        railway_quelle="foreman, backend",
        uebernehmen=_SUBSTRAT
        | _PSEUDO_SCHALTER
        | frozenset(
            {
                "ENVIRONMENT",
                "FOREMAN_ARCHIVE_SUBSTRATE_ENABLED",
                "FOREMAN_EMBED_DIMENSION",
                "FOREMAN_EMBED_OPENAI_API_KEY",
                "FOREMAN_EMBED_OPENAI_MODEL",
                "FOREMAN_EMBED_PRIORITY",
                "FOREMAN_LLM_CLOUD_API_KEY",
                "FOREMAN_LLM_CLOUD_MODEL",
                "FOREMAN_LLM_MAX_TOKENS",
                "FOREMAN_LLM_PRIORITY",
                "FOREMAN_LLM_RATE_LIMIT_CAPACITY",
                "FOREMAN_LLM_RATE_LIMIT_REFILL_PER_S",
                "FOREMAN_MCP_TOKEN",
                "JWT_ALGORITHM",
                "JWT_SECRET",
                "SUBSTRATE_NAMESPACE",
                "SUBSTRATE_TIMEOUT_S",
            }
        ),
        nicht_uebernommen=_SERVER_ANDERS,
    ),
    "worker": Dienst(
        konfig="worker.conf.env",
        railway_quelle="foreman, live-worker",
        uebernehmen=_SUBSTRAT | _PSEUDO_SCHALTER,
        nicht_uebernommen={
            **_SERVER_ANDERS,
            "ENVIRONMENT": "auf dem Server in deploy/konfig (worker.conf.env)",
        },
    ),
}


# ── Lesen ────────────────────────────────────────────────────────────────────


def konfig_namen(pfad: Path) -> frozenset[str]:
    """Die Namen, die eine Datei unter deploy/konfig setzt."""
    namen: set[str] = set()
    for nummer, zeile in enumerate(pfad.read_text(encoding="utf-8").splitlines(), start=1):
        if not zeile.strip() or zeile.lstrip().startswith("#"):
            continue
        name, gleich, _ = zeile.partition("=")
        if not gleich or not NAME_MUSTER.match(name):
            raise BefundError(f"{pfad.name}:{nummer}: keine Zuweisung NAME=wert")
        if name in namen:
            raise BefundError(f"{pfad.name}:{nummer}: {name} steht doppelt")
        namen.add(name)
    return frozenset(namen)


def railway_lesen(roh: bytes) -> dict[str, str | None]:
    """Ausgabe von ``railway variables --json``; versiegelte Werte sind None."""
    text = roh.decode("utf-8").removeprefix("﻿")
    try:
        daten = json.loads(text)
    except json.JSONDecodeError as exc:
        # exc.msg trägt keinen Ausschnitt der Eingabe
        raise BefundError(
            f"Eingabe ist kein JSON ({exc.msg}, Zeile {exc.lineno}) — railway variables --json"
        ) from None
    if not isinstance(daten, dict) or not daten:
        raise BefundError("Eingabe ist kein JSON-Objekt mit Variablen — railway variables --json")
    falsch = sorted(
        n
        for n, w in daten.items()
        if not NAME_MUSTER.match(n) or not (w is None or isinstance(w, str))
    )
    if falsch:
        raise BefundError(f"Unerwartete Einträge in der Eingabe: {', '.join(falsch)}")
    return daten


def env_lesen(pfad: Path) -> dict[str, str]:
    """Liest eine Datei, die dieses Skript geschrieben hat (NAME='wert')."""
    werte: dict[str, str] = {}
    for nummer, zeile in enumerate(pfad.read_text(encoding="utf-8").splitlines(), start=1):
        if not zeile.strip() or zeile.startswith("#"):
            continue
        name, gleich, rest = zeile.partition("=")
        if (
            not gleich
            or not NAME_MUSTER.match(name)
            or len(rest) < 2
            or rest[0] != "'"
            or rest[-1] != "'"
        ):
            raise BefundError(f"{pfad.name}:{nummer}: nicht im Format NAME='wert'")
        werte[name] = rest[1:-1]
    return werte


# ── Prüfen ───────────────────────────────────────────────────────────────────


def wert_problem(wert: str) -> str | None:
    """Warum ein Wert nicht einfach quotiert in eine Compose-Datei passt."""
    if not wert:
        return "ist leer"
    if "'" in wert:
        return "enthält ein einfaches Anführungszeichen"
    if any(zeichen in wert for zeichen in "\n\r\0"):
        return "enthält einen Zeilenumbruch oder ein Nullzeichen"
    if wert.endswith("\\"):
        return "endet mit einem Backslash"
    return None


def werte_pruefen(namen: list[str], railway: dict[str, str | None]) -> list[str]:
    """Jeder Name muss auf Railway stehen, auslesbar sein und in die Datei passen."""
    befunde: list[str] = []
    for name in namen:
        wert = railway.get(name)
        if name not in railway:
            befunde.append(f"{name}: fehlt auf Railway")
        elif wert is None:
            befunde.append(f"{name}: auf Railway versiegelt, nicht auslesbar — von Hand setzen")
        elif problem := wert_problem(wert):
            befunde.append(f"{name}: Wert {problem}")
    return befunde


def einordnen(dienst: Dienst, railway: dict[str, str | None]) -> tuple[list[str], list[str]]:
    """(Namen für pseudo.env, Befunde zu nicht eingeordneten Namen)."""
    pseudo = sorted(n for n in railway if PSEUDO_MUSTER.match(n))
    bekannt = dienst.uebernehmen | dienst.nicht_uebernommen.keys() | NIE_UEBERNEHMEN
    unbekannt = [
        f"{name}: nicht eingeordnet — in deploy/server/geheimnisse.py aufnehmen"
        for name in sorted(railway)
        if name not in bekannt and name not in pseudo and not name.startswith(RAILWAY_PRAEFIX)
    ]
    if not pseudo:
        unbekannt.append("FOREMAN_PSEUDO_KEY_v<N>: kein Schlüssel auf Railway")
    return pseudo, unbekannt


def zu_offen(modus: int) -> bool:
    """Gruppe oder andere haben irgendein Recht."""
    return bool(stat.S_IMODE(modus) & 0o077)


def verzeichnis_pruefen(ziel: Path) -> None:
    if not ziel.is_dir():
        raise BefundError(f"{ziel} fehlt — install -d -m 700 {ziel}")
    if os.name == "posix" and zu_offen(ziel.stat().st_mode):
        raise BefundError(
            f"{ziel} ist für andere zugänglich (Modus {stat.S_IMODE(ziel.stat().st_mode):o}) — chmod 700"
        )


# ── Schreiben ────────────────────────────────────────────────────────────────


def env_text(werte: dict[str, str], herkunft: str) -> str:
    zeilen = [f"# {herkunft} — geschrieben von deploy/server/geheimnisse.py, nie ins Repository"]
    zeilen += [f"{name}='{wert}'" for name, wert in sorted(werte.items())]
    return "\n".join(zeilen) + "\n"


def datei_anlegen(pfad: Path, text: str) -> None:
    """Legt die Datei neu an (O_EXCL, Modus 600) — eine vorhandene bleibt unberührt."""
    fd = os.open(pfad, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as datei:
            datei.write(text)
            datei.flush()
            os.fsync(datei.fileno())
    except BaseException:
        pfad.unlink(missing_ok=True)
        raise


def schreiben_oder_vergleichen(pfad: Path, werte: dict[str, str], herkunft: str) -> None:
    if not pfad.exists():
        datei_anlegen(pfad, env_text(werte, herkunft))
        print(f"✅ {pfad} angelegt: {len(werte)} Einträge (Modus 600)")
        return
    if os.name == "posix" and zu_offen(pfad.stat().st_mode):
        raise BefundError(f"{pfad} ist für andere lesbar — chmod 600")
    vorhanden = env_lesen(pfad)
    abweichend = sorted(
        n for n in vorhanden.keys() | werte.keys() if vorhanden.get(n) != werte.get(n)
    )
    if abweichend:
        raise BefundError(
            f"{pfad} weicht ab: {', '.join(abweichend)} — nicht überschrieben. "
            "Ist Railway der gültige Stand: Datei von Hand entfernen und erneut übernehmen"
        )
    print(f"✅ {pfad} unverändert: {len(werte)} Einträge wie auf Railway")


def zugaenge() -> dict[str, dict[str, str]]:
    """Ein neues Datenbank-Passwort und die Adresse, die es trägt — je Zieldatei."""
    passwort = secrets.token_urlsafe(PASSWORT_BYTES)
    return {
        "timescaledb.env": {"POSTGRES_PASSWORD": passwort},
        "zugang.env": {
            "DATABASE_URL": f"postgresql+asyncpg://{PG_ROLLE}:{passwort}@{PG_HOST}/{PG_DATENBANK}"
        },
    }


# ── Befehle ──────────────────────────────────────────────────────────────────


def anlegen(ziel: Path) -> None:
    verzeichnis_pruefen(ziel)
    dateien = zugaenge()
    vorhanden = sorted(name for name in dateien if (ziel / name).exists())
    if vorhanden:
        raise BefundError(
            f"Gibt es schon: {', '.join(vorhanden)} — nichts angelegt (anlegen läuft nur einmal)"
        )
    geschrieben: list[Path] = []
    try:
        for name, werte in dateien.items():
            datei_anlegen(ziel / name, env_text(werte, "Zugang nur auf diesem Server"))
            geschrieben.append(ziel / name)
    except BaseException:
        for pfad in geschrieben:
            pfad.unlink(missing_ok=True)
        raise
    print(f"✅ Angelegt in {ziel}: {', '.join(dateien)} (Modus 600)")


def uebernehmen(dienst_name: str, roh: bytes, ziel: Path, konfig_verzeichnis: Path) -> None:
    dienst = DIENSTE[dienst_name]
    verzeichnis_pruefen(ziel)
    doppelt = sorted(konfig_namen(konfig_verzeichnis / dienst.konfig) & dienst.uebernehmen)
    if doppelt:
        raise BefundError(
            f"{dienst.konfig} und die Liste von {dienst_name} teilen: {', '.join(doppelt)}"
        )
    railway = railway_lesen(roh)
    pseudo, befunde = einordnen(dienst, railway)
    befunde += werte_pruefen(sorted(dienst.uebernehmen) + pseudo, railway)
    if befunde:
        zeilen = "\n".join(f"   {befund}" for befund in befunde)
        raise BefundError(
            f"Erwartet: Railway {dienst.railway_quelle}. {len(befunde)} Befunde, nichts geschrieben:\n{zeilen}"
        )
    for name in sorted(railway.keys() & dienst.nicht_uebernommen.keys()):
        print(f"📋 {name}: nicht übernommen — {dienst.nicht_uebernommen[name]}")
    herkunft = f"Von Railway übernommen ({dienst.railway_quelle})"
    schluessel = {name: railway[name] or "" for name in pseudo}
    schreiben_oder_vergleichen(ziel / PSEUDO_DATEI, schluessel, herkunft)
    werte = {name: railway[name] or "" for name in dienst.uebernehmen}
    schreiben_oder_vergleichen(ziel / f"{dienst_name}.env", werte, herkunft)


def eingabe_lesen(strom: IO[bytes]) -> bytes:
    roh = strom.read(EINGABE_GRENZE + 1)
    if len(roh) > EINGABE_GRENZE:
        raise BefundError(f"Eingabe größer als {EINGABE_GRENZE} Bytes — keine Variablenliste")
    return roh


def main(argv: list[str] | None = None, stdin: IO[bytes] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Geheimnisdateien für den FOREMAN-Server")
    parser.add_argument(
        "--ziel", type=Path, default=ENV_VERZEICHNIS, help=f"Vorgabe: {ENV_VERZEICHNIS}"
    )
    parser.add_argument("--konfig", type=Path, default=KONFIG_VERZEICHNIS, help=argparse.SUPPRESS)
    befehle = parser.add_subparsers(dest="befehl", required=True)
    befehle.add_parser("anlegen", help="Datenbank-Zugang erzeugen")
    befehl_uebernehmen = befehle.add_parser(
        "uebernehmen", help="railway variables --json von stdin übernehmen"
    )
    befehl_uebernehmen.add_argument("dienst", choices=sorted(DIENSTE))
    args = parser.parse_args(argv)
    try:
        if args.befehl == "anlegen":
            anlegen(args.ziel)
        else:
            strom = stdin if stdin is not None else sys.stdin.buffer
            if strom.isatty():
                raise BefundError(
                    "Keine Eingabe — railway variables --json … | ssh … geheimnisse.py uebernehmen <dienst>"
                )
            uebernehmen(args.dienst, eingabe_lesen(strom), args.ziel, args.konfig)
    except BefundError as befund:
        print(f"❌ {befund}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
