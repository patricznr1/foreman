#!/usr/bin/env python3
# ============================================================
#  FOREMAN — .claude/hooks/pre-push-walkthrough.py
#  Zweck: Trägt die Spielregel aus docs/WALKTHROUGH.md ("jeder bauende Commit
#         ergänzt das Dokument"), die als Text zwanzigmal gerissen ist: Zwischen
#         dem 28.08. und dem 07.09.2026 gingen 20 Commits an src/foreman und
#         frontend nach main, keiner zog den WALKTHROUGH nach. Der Hook prüft am
#         Übergang nach draussen (git push), ob der Zweig Anwendungscode mitbringt,
#         ohne den WALKTHROUGH zu berühren — und sperrt dann, mit Ausweg.
#  Warum am Push und nicht am Commit: Ein Zweig darf in Etappen wachsen; was
#         zählt, ist der Stand, der das Haus verlässt. Dieselbe Stelle, an der
#         auch die Registerzahlen geprüft werden (GROUND_TRUTH §23.1).
#  Ausweg: `# Walkthrough-Ausnahme: <grund>` im Push-Befehl — sichtbar im
#         Transkript, damit die Ausnahme eine Entscheidung ist und kein Vergessen.
#  Architektur-Einordnung: Projekt-Hook (Claude Code PreToolUse, Bash). Kein
#         Anwendungscode; nur Standardbibliothek, damit er ohne .venv läuft.
# ============================================================
"""Sperrt `git push`, wenn Anwendungscode ohne WALKTHROUGH-Nachtrag das Haus verlässt.

Aufruf durch Claude Code (stdin: JSON mit tool_name/tool_input). Rückgabe:
Exit 0 = durchlassen, Exit 2 = sperren (stderr geht an das Modell).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

WALKTHROUGH = "docs/WALKTHROUGH.md"
# Anwendungscode, der eine Erklärung im WALKTHROUGH verdient. Tests und reine
# Konfiguration nicht — sie erklären nichts, was ein Nicht-Coder lesen müsste.
BAUENDE_PFADE = ("src/foreman/", "frontend/app/", "frontend/components/", "frontend/lib/")
NICHT_BAUEND = re.compile(r"(^|/)(tests?/|.*\.test\.[jt]sx?$|.*\.spec\.[jt]sx?$|testing/)")
AUSNAHME = re.compile(r"#\s*Walkthrough-Ausnahme:\s*\S")
PUSH = re.compile(r"(^|[;&|]\s*)git\s+push\b")


def _git(*args: str, cwd: Path) -> str:
    ergebnis = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return ergebnis.stdout if ergebnis.returncode == 0 else ""


def _geaenderte_dateien(cwd: Path) -> set[str]:
    """Alles, was der Zweig gegenüber main mitbringt — committet, vorgemerkt und offen."""
    basis = (
        _git("merge-base", "HEAD", "origin/main", cwd=cwd).strip()
        or _git("merge-base", "HEAD", "main", cwd=cwd).strip()
    )
    dateien: set[str] = set()
    if basis:
        dateien.update(_git("diff", "--name-only", f"{basis}...HEAD", cwd=cwd).split())
    dateien.update(_git("diff", "--name-only", "HEAD", cwd=cwd).split())
    return {d.replace("\\", "/") for d in dateien if d}


def main() -> int:
    try:
        eingabe = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0
    if eingabe.get("tool_name") != "Bash":
        return 0
    befehl = str(eingabe.get("tool_input", {}).get("command", ""))
    if not PUSH.search(befehl) or "--dry-run" in befehl or AUSNAHME.search(befehl):
        return 0

    cwd = Path(eingabe.get("cwd") or Path.cwd())
    wurzel = _git("rev-parse", "--show-toplevel", cwd=cwd).strip()
    if not wurzel or not (Path(wurzel) / WALKTHROUGH).exists():
        return 0  # anderes Repo — der Hook ist nur für FOREMAN gedacht

    dateien = _geaenderte_dateien(Path(wurzel))
    bauend = sorted(
        d for d in dateien if d.startswith(BAUENDE_PFADE) and not NICHT_BAUEND.search(d)
    )
    if not bauend or WALKTHROUGH in dateien:
        return 0

    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass  # umgeleiteter Strom (Kontrollpunkt, Tests) — die Meldung zählt, nicht die Kodierung
    print(
        "WALKTHROUGH-Pflicht: Der Zweig bringt Anwendungscode mit, docs/WALKTHROUGH.md "
        "bleibt unberührt. Die Spielregel im Dokumentkopf verlangt den Nachtrag im "
        "selben Arbeitsgang.\n"
        f"  Betroffen ({len(bauend)}): "
        + ", ".join(bauend[:8])
        + (" …" if len(bauend) > 8 else "")
        + "\n"
        "RICHTIG: den passenden Abschnitt im WALKTHROUGH ergänzen (Was tut es? / Warum "
        "existiert es?), dann erneut pushen.\n"
        "AUSWEG, wenn die Änderung nichts erklärt (Umbenennung, Wording, Fehlerbehebung "
        "ohne neues Verhalten): `# Walkthrough-Ausnahme: <grund>` in den Push-Befehl.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
