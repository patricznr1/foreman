#!/usr/bin/env python3
# ============================================================
#  FOREMAN — .claude/hooks/pre-push-walkthrough.py
#  Zweck: Trägt die Spielregel aus docs/WALKTHROUGH.md ("jeder bauende Commit
#         ergänzt das Dokument"), die als Text zwanzigmal gerissen ist: Zwischen
#         dem 28.08. und dem 07.09.2026 gingen 20 Commits an src/foreman und
#         frontend nach main, keiner zog den WALKTHROUGH nach. Der Hook prüft am
#         Übergang nach draussen (git push), ob das, was geht, Anwendungscode
#         mitbringt, ohne den WALKTHROUGH zu berühren — und sperrt dann, mit Ausweg.
#  Warum am Push und nicht am Commit: Ein Zweig darf in Etappen wachsen; was
#         zählt, ist der Stand, der das Haus verlässt. Dieselbe Stelle, an der
#         auch die Registerzahlen geprüft werden (GROUND_TRUTH §23.1).
#  Was zählt: nur Committetes, und zwar auf dem Ref, den der Push trägt — die
#         Refspec (`origin feature/x`, `HEAD~1:refs/heads/y`, `--all`), sonst HEAD.
#         Löschungen (`--delete`, `:ref`) und `--tags` tragen keinen Zweig. Eine
#         offene Änderung am WALKTHROUGH ist kein Nachtrag (die Meldung sagt das),
#         offener Anwendungscode kein Grund zu sperren. Das Repo ist das, in dem
#         der Push läuft: `-C <pfad>` / `--work-tree` zählen, nicht nur `cwd`.
#  Wie ein Push erkannt wird: je Teilbefehl, an seiner Form. Getrennt wird an
#         && || ; | & ( ) ` und Zeilenumbruch ausserhalb von Anführungszeichen;
#         Backslash ist Escape und Zeilenfortsetzung; Kommentare hinter # und
#         Heredoc-Rümpfe (<<EOF … EOF) sind keine Befehle. Vor dem Programm dürfen
#         Variablenzuweisungen (GIT_TERMINAL_PROMPT=0) und Schlüsselwörter (if, !,
#         do) stehen; Vorschalter (timeout, sudo, env, command, winpty …) und
#         Schalen (sh -c "…", cmd /c …) werden aufgelöst. Erkannt wird `git`
#         (auch als Pfad oder git.exe), davor beliebige git-Optionen, dann `push`.
#         Ein Trockenlauf stellt nur seinen Teilbefehl frei, und wie bei git
#         gewinnt die letzte Option (`--no-dry-run`); -h/--help pushen nichts.
#         Dieselbe Bauart wie die Zerlegung in AEOS, hier ohne Abhängigkeit,
#         damit der Hook ohne .venv läuft.
#  Grenzen, bewusst: ein git-Alias (`-c alias.p=push p`), ein Push aus Python
#         (subprocess) oder mit `push` aus stdin (`echo push | xargs git`) wird
#         nicht gesehen; ein WALKTHROUGH-Commit zählt an der Berührung, nicht am
#         Inhalt; ist keine Basis zu main bestimmbar (fremdes Remote, Orphan),
#         lässt der Hook durch. Belegt von drei Skeptikern am 07.09.2026.
#  Ausweg: `# Walkthrough-Ausnahme: <grund>` im Push-Befehl — sichtbar im
#         Transkript, damit die Ausnahme eine Entscheidung ist und kein Vergessen.
#  Architektur-Einordnung: Projekt-Hook (Claude Code PreToolUse, Bash). Kein
#         Anwendungscode; nur Standardbibliothek. Tests:
#         tests/unit/test_pre_push_walkthrough.py.
# ============================================================
"""Sperrt `git push`, wenn Anwendungscode ohne WALKTHROUGH-Nachtrag das Haus verlässt.

Aufruf durch Claude Code (stdin: JSON mit tool_name/tool_input). Rückgabe:
Exit 0 = durchlassen, Exit 2 = sperren (stderr geht an das Modell).
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

WALKTHROUGH = "docs/WALKTHROUGH.md"
# Anwendungscode, der eine Erklärung im WALKTHROUGH verdient. Tests und reine
# Konfiguration nicht — sie erklären nichts, was ein Nicht-Coder lesen müsste.
BAUENDE_PFADE = ("src/foreman/", "frontend/app/", "frontend/components/", "frontend/lib/")
NICHT_BAUEND = re.compile(
    r"(^|/)(tests?/|__tests__/|testing/|conftest\.py$|.*\.test\.[jt]sx?$|.*\.spec\.[jt]sx?$)"
)
AUSNAHME = re.compile(r"#\s*Walkthrough-Ausnahme:\s*\S")
# git-Optionen, die VOR dem Unterbefehl stehen und einen eigenen Wert tragen.
GIT_OPTION_MIT_WERT = frozenset(
    {"-C", "-c", "--git-dir", "--work-tree", "--exec-path", "--namespace", "--config-env"}
)
# Push-Optionen mit eigenem Wert — damit der Wert nicht als Refspec gilt.
PUSH_OPTION_MIT_WERT = frozenset({"-o", "--push-option", "--repo", "--receive-pack", "--exec"})
# Schalen: der Befehl steckt gequotet in einem Wort (sh -c "…", cmd /c "…").
SCHALEN = frozenset({"sh", "bash", "zsh", "dash", "pwsh", "powershell", "cmd"})
# Vorschalter: der Befehl folgt ungequotet (timeout 30 git push …).
VORSCHALTER = frozenset(
    {"timeout", "env", "nice", "nohup", "sudo", "xargs", "command", "exec", "time", "winpty"}
)
# Was die Shell vor dem Programm duldet und was hier keinen Befehl beginnt.
SCHLUESSELWOERTER = frozenset({"if", "then", "else", "elif", "do", "while", "until", "!", "{", "}"})
VARIABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
TRENNER = frozenset("\n;|&()`")


class Push(NamedTuple):
    """Ein `git push`-Teilbefehl: wo er läuft (aus -C/--work-tree) und womit."""

    verzeichnis: str | None
    argumente: tuple[str, ...]


# --- Zerlegung: was ein echter Push ist ---------------------------------------


def _ohne_heredocs(befehl: str) -> str:
    """Heredoc-Rümpfe sind Daten, keine Befehle: die Zeilen bis zur Endmarke fallen weg."""
    aus: list[str] = []
    marke: str | None = None
    for zeile in befehl.split("\n"):
        if marke is not None:
            if zeile.strip() == marke:
                marke = None
            continue
        aus.append(zeile)
        treffer = HEREDOC.search(zeile)
        if treffer:
            marke = treffer.group(2)
    return "\n".join(aus)


def _teilbefehle(befehl: str) -> list[str]:
    """Trennt an && || ; | & ( ) ` und Zeilenumbruch — ausserhalb von Anführungszeichen.

    Backslash ist Escape (ausserhalb einfacher Anführungszeichen) und vor dem
    Zeilenumbruch Fortsetzung; ein # nach Leerraum beginnt einen Kommentar.
    """
    text = _ohne_heredocs(befehl).replace("\\\n", " ")
    teile: list[str] = []
    aktuell: list[str] = []
    quote: str | None = None
    i = 0
    while i < len(text):
        zeichen = text[i]
        if quote == "'":
            aktuell.append(zeichen)
            if zeichen == "'":
                quote = None
        elif zeichen == "\\" and i + 1 < len(text):
            aktuell.append(zeichen)
            aktuell.append(text[i + 1])
            i += 2
            continue
        elif quote == '"':
            aktuell.append(zeichen)
            if zeichen == '"':
                quote = None
        elif zeichen in ("'", '"'):
            quote = zeichen
            aktuell.append(zeichen)
        elif zeichen == "#" and (not aktuell or aktuell[-1].isspace()):
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        elif zeichen in TRENNER:
            teile.append("".join(aktuell))
            aktuell = []
        else:
            aktuell.append(zeichen)
        i += 1
    teile.append("".join(aktuell))
    return [t for t in (t.strip() for t in teile) if t]


def _woerter(teil: str) -> list[str]:
    try:
        return shlex.split(teil, posix=True)
    except ValueError:  # unpaariges Anführungszeichen — grob zerlegen statt aufgeben
        return teil.split()


def _programmname(wort: str) -> str:
    name = wort.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def _ist_git(wort: str) -> bool:
    return _programmname(wort) == "git"


def _ohne_vorspann(woerter: list[str]) -> list[str]:
    """Schlüsselwörter und Variablenzuweisungen vor dem Programm abstreifen."""
    i = 0
    while i < len(woerter) and (woerter[i] in SCHLUESSELWOERTER or VARIABLE.match(woerter[i])):
        i += 1
    return woerter[i:]


def _push(woerter: list[str]) -> Push | None:
    """Der Push, wenn die Wörter ein `git [optionen] push …` sind; sonst None."""
    if not woerter or not _ist_git(woerter[0]):
        return None
    verzeichnis: str | None = None
    i = 1
    while i < len(woerter) and woerter[i].startswith("-"):
        wort = woerter[i]
        if wort in GIT_OPTION_MIT_WERT:
            wert = woerter[i + 1] if i + 1 < len(woerter) else ""
            if wort == "-C":
                verzeichnis = str(Path(verzeichnis) / wert) if verzeichnis else wert
            elif wort == "--work-tree":
                verzeichnis = wert
            elif wort == "--git-dir" and verzeichnis is None:
                verzeichnis = str(Path(wert).parent)
            i += 2
            continue
        if wort.startswith("--work-tree="):
            verzeichnis = wort.split("=", 1)[1]
        elif wort.startswith("--git-dir=") and verzeichnis is None:
            verzeichnis = str(Path(wort.split("=", 1)[1]).parent)
        i += 1
    if i >= len(woerter) or woerter[i] != "push":
        return None
    return Push(verzeichnis, tuple(woerter[i + 1 :]))


def _pushes_aus_woertern(woerter: list[str]) -> list[Push]:
    woerter = _ohne_vorspann(woerter)
    if not woerter:
        return []
    push = _push(woerter)
    if push is not None:
        return [push]
    kopf = _programmname(woerter[0])
    if kopf not in SCHALEN and kopf not in VORSCHALTER:
        return []
    gefunden: list[Push] = []
    if kopf in SCHALEN:
        # `sh -c "git push …"`: der Befehl steckt gequotet in einem Wort.
        for wort in woerter[1:]:
            if any(z.isspace() for z in wort):
                gefunden.extend(_pushes(wort))
    # `timeout 30 git push …`, `sudo bash -c "…"`: der Befehl folgt ungequotet —
    # ab dem ersten Wort, das git oder wieder ein Vorschalter ist.
    rest = woerter[1:]
    for k, wort in enumerate(rest):
        name = _programmname(wort)
        if name == "git" or name in SCHALEN or name in VORSCHALTER:
            gefunden.extend(_pushes_aus_woertern(rest[k:]))
            break
    return gefunden


def _pushes(befehl: str) -> list[Push]:
    """Alle `git push`-Teilbefehle, Vorschalter und Schalen aufgelöst."""
    gefunden: list[Push] = []
    for teil in _teilbefehle(befehl):
        gefunden.extend(_pushes_aus_woertern(_woerter(teil)))
    return gefunden


def _pusht_nichts(argumente: tuple[str, ...]) -> bool:
    """Trockenlauf oder Hilfe — wie bei git gewinnt die letzte Option."""
    trocken = False
    for a in argumente:
        if a == "--":
            break
        if a == "--dry-run":
            trocken = True
        elif a == "--no-dry-run":
            trocken = False
        elif a in ("--help", "-h"):
            return True
        elif a.startswith("-") and not a.startswith("--") and "n" in a[1:]:
            trocken = True  # Kurzflag, auch im Bündel (-nv): n steht bei push nur für --dry-run
    return trocken


def echte_pushes(befehl: str) -> list[Push]:
    return [p for p in _pushes(befehl) if not _pusht_nichts(p.argumente)]


def enthaelt_echten_push(befehl: str) -> bool:
    """Mindestens ein Teilbefehl ist ein `git push`, der etwas überträgt."""
    return bool(echte_pushes(befehl))


def _positionen_und_flags(argumente: tuple[str, ...]) -> tuple[list[str], set[str]]:
    """Trennt Push-Argumente in Positionen (Remote, Refspecs) und Flags."""
    positionen: list[str] = []
    flags: set[str] = set()
    i = 0
    while i < len(argumente):
        a = argumente[i]
        if a == "--":
            positionen.extend(argumente[i + 1 :])
            break
        if a in PUSH_OPTION_MIT_WERT:
            i += 1
        elif a.startswith("-"):
            flags.add(a)
        else:
            positionen.append(a)
        i += 1
    return positionen, flags


def _quellen(argumente: tuple[str, ...]) -> list[str]:
    """Die lokalen Refs, die dieser Push trägt.

    Ohne Refspec ist es HEAD; `--all`/`--mirror`/`--branches` heisst jeder
    lokale Zweig (`*`); Löschungen und reine Tag-Pushes tragen keinen Zweig.
    """
    positionen, flags = _positionen_und_flags(argumente)
    if flags & {"--delete", "-d"}:
        return []
    if flags & {"--all", "--mirror", "--branches"}:
        return ["*"]
    refspecs = positionen[1:]  # die erste Position ist das Remote
    if not refspecs:
        return [] if "--tags" in flags else ["HEAD"]
    quellen = [refspec.lstrip("+").split(":", 1)[0] for refspec in refspecs]
    return [q for q in quellen if q]


# --- Was den Rechner verlässt ------------------------------------------------


def _git(*args: str, cwd: Path) -> str:
    try:
        ergebnis = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:  # cwd gibt es nicht, git fehlt — dann gibt es auch nichts zu prüfen
        return ""
    return ergebnis.stdout if ergebnis.returncode == 0 else ""


def _pfade(ausgabe: str) -> set[str]:
    """NUL-getrennte Ausgabe von `git … -z`: Leerzeichen und Umlaute bleiben ganz."""
    return {d.replace("\\", "/") for d in ausgabe.split("\0") if d}


def _basis(wurzel: Path, ref: str) -> str:
    return (
        _git("merge-base", ref, "origin/main", cwd=wurzel).strip()
        or _git("merge-base", ref, "main", cwd=wurzel).strip()
    )


def _committete_dateien(wurzel: Path, ref: str) -> set[str]:
    """Was `ref` gegenüber main mitbringt — nur Committetes, denn nur das pusht.

    `--no-renames`: eine Verschiebung aus src/foreman heraus zeigt beide Seiten,
    sonst verschwände der Weggang hinter dem Zielpfad.
    """
    basis = _basis(wurzel, ref)
    if not basis:
        return set()
    return _pfade(_git("diff", "--name-only", "-z", "--no-renames", f"{basis}..{ref}", cwd=wurzel))


def _offene_dateien(wurzel: Path) -> set[str]:
    """Vorgemerkt oder geändert, aber nicht committet — für den Hinweis, nicht fürs Gate."""
    return _pfade(_git("diff", "--name-only", "-z", "HEAD", cwd=wurzel))


def _zweige(wurzel: Path) -> list[str]:
    return _git("for-each-ref", "--format=%(refname:short)", "refs/heads", cwd=wurzel).split()


def _bauend(dateien: set[str]) -> list[str]:
    return sorted(d for d in dateien if d.startswith(BAUENDE_PFADE) and not NICHT_BAUEND.search(d))


def _repo_wurzel(cwd: Path, push: Push) -> Path | None:
    ort = cwd
    if push.verzeichnis:
        kandidat = cwd / push.verzeichnis
        if kandidat.is_dir():
            ort = kandidat
    wurzel = _git("rev-parse", "--show-toplevel", cwd=ort).strip()
    if not wurzel or not (Path(wurzel) / WALKTHROUGH).exists():
        return None  # anderes Repo — der Hook ist nur für FOREMAN gedacht
    return Path(wurzel)


def main() -> int:
    try:
        eingabe = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0
    if eingabe.get("tool_name") != "Bash":
        return 0
    befehl = str(eingabe.get("tool_input", {}).get("command", ""))
    pushes = echte_pushes(befehl)
    if not pushes or AUSNAHME.search(befehl):
        return 0

    cwd = Path(eingabe.get("cwd") or Path.cwd())
    for push in pushes:
        wurzel = _repo_wurzel(cwd, push)
        if wurzel is None:
            continue
        quellen = _quellen(push.argumente)
        if quellen == ["*"]:
            quellen = _zweige(wurzel)
        for quelle in quellen:
            committet = _committete_dateien(wurzel, quelle)
            bauend = _bauend(committet)
            if not bauend or WALKTHROUGH in committet:
                continue
            return _sperre(wurzel, quelle, bauend)
    return 0


def _ist_ausgecheckt(wurzel: Path, ref: str) -> bool:
    """Zeigt `ref` auf den Stand der Arbeitskopie? Nur dann ist ein offener Nachtrag ein Hinweis."""
    kopf = _git("rev-parse", "--verify", "HEAD", cwd=wurzel).strip()
    return bool(kopf) and _git("rev-parse", "--verify", ref, cwd=wurzel).strip() == kopf


def _sperre(wurzel: Path, quelle: str, bauend: list[str]) -> int:
    name = _git("rev-parse", "--abbrev-ref", quelle, cwd=wurzel).strip() or quelle
    hinweis = (
        f"  {WALKTHROUGH} ist geändert, aber nicht committet — der Push trägt den Stand "
        "von HEAD, nicht den der Arbeitskopie.\n"
        if _ist_ausgecheckt(wurzel, quelle) and WALKTHROUGH in _offene_dateien(wurzel)
        else ""
    )
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass  # umgeleiteter Strom (Kontrollpunkt, Tests) — die Meldung zählt, nicht die Kodierung
    print(
        f"WALKTHROUGH-Pflicht: Der Zweig {name} bringt Anwendungscode mit, docs/WALKTHROUGH.md "
        "bleibt unberührt. Die Spielregel im Dokumentkopf verlangt den Nachtrag im "
        "selben Arbeitsgang.\n"
        f"  Betroffen ({len(bauend)}): "
        + ", ".join(bauend[:8])
        + (" …" if len(bauend) > 8 else "")
        + "\n"
        + hinweis
        + "RICHTIG: den passenden Abschnitt im WALKTHROUGH ergänzen (Was tut es? / Warum "
        "existiert es?), committen, dann erneut pushen.\n"
        "AUSWEG, wenn die Änderung nichts erklärt (Umbenennung, Wording, Fehlerbehebung "
        "ohne neues Verhalten): `# Walkthrough-Ausnahme: <grund>` in den Push-Befehl.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
