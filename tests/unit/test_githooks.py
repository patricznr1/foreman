# ══════════════════════════════════════════════════════════════
# FOREMAN — Git-Hooks sind ausführbar hinterlegt
# Ein Hook ohne Ausführungsbit ist auf Linux und macOS wirkungslos.
# ══════════════════════════════════════════════════════════════
"""Hält fest, dass `.githooks/pre-commit` im Index als 100755 steht.

WARUM DAS NICHT SELBSTVERSTÄNDLICH IST. Unter Windows steht `core.fileMode` auf
`false`; Git ignoriert das Ausführungsbit der Arbeitskopie dann vollständig. Ein
`chmod +x` wirkt lokal, landet aber nicht im Index — die Datei wird als 100644
eingetragen. Auf dieser Plattform fällt das nicht auf, weil Git für Windows
Hooks ohnehin über `sh` startet. Auf Linux und macOS führt Git eine Datei ohne
Ausführungsbit nicht aus, und der Hook schweigt: Das Wächter-Protokoll würde
weder geprüft noch aufgenommen, ohne dass jemand etwas bemerkt.

Genau so passiert (09.09.2026, im Review gefunden): Der Hook wurde mit gesetztem
Bit in der Arbeitskopie, aber als 100644 im Index committet.

WARUM GEGEN DEN INDEX UND NICHT GEGEN DIE DATEI. `Path.stat()` liest die
Arbeitskopie, und die sagt unter Windows nichts über das aus, was im Repository
steht. Maßgeblich ist der Modus, den ein anderer Klon bekommt — und der steht im
Index.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[2]
HOOKS = WURZEL / ".githooks"


def _index_modus(pfad: str) -> str:
    """Der Dateimodus, wie er im Git-Index steht (nicht in der Arbeitskopie)."""
    lauf = subprocess.run(
        ["git", "-C", str(WURZEL), "ls-files", "-s", pfad],
        capture_output=True,
        text=True,
        check=True,
    )
    if not lauf.stdout.strip():
        pytest.fail(f"{pfad} ist nicht im Index — der Hook wäre in keinem Klon vorhanden")
    return lauf.stdout.split()[0]


def test_pre_commit_ist_ausfuehrbar_hinterlegt() -> None:
    """Der Hook steht als 100755 im Index.

    Bei 100644 startet Git ihn auf Linux und macOS nicht, und die Prüfung des
    Wächter-Protokolls fällt still aus.
    """
    assert _index_modus(".githooks/pre-commit") == "100755"


def test_jeder_hook_ist_ausfuehrbar_hinterlegt() -> None:
    """Dieselbe Zusicherung für alles, was künftig unter .githooks/ dazukommt.

    Ohne diesen Test gälte sie nur für die eine Datei, die es beim Schreiben gab —
    und ein zweiter Hook brächte denselben Fehler unbemerkt zurück.
    """
    hooks = [p for p in HOOKS.iterdir() if p.is_file()] if HOOKS.is_dir() else []
    assert hooks, ".githooks/ ist leer oder fehlt"
    falsch = [p.name for p in hooks if _index_modus(f".githooks/{p.name}") != "100755"]
    assert not falsch, f"nicht ausführbar hinterlegt: {falsch}"
