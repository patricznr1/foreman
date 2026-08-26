# ══════════════════════════════════════════════════════════════
# FOREMAN — Der Betrieb schaltet `assert` nicht ab
# Die verbliebenen Zusicherungen dürfen bleiben, WEIL das hier eingefordert wird.
# ══════════════════════════════════════════════════════════════
"""Hält die Annahme fest, auf der die verbliebenen `assert`-Anweisungen ruhen.

WORUM ES GEHT. Sechs Stellen im Quelltext führen `assert`, um eine Invariante für
die Typprüfung festzuhalten — etwa dass ein Wert nach der vorangegangenen
Zuweisung nicht mehr leer sein kann. Das ist eine legitime Verwendung: Die
Anweisung dokumentiert eine Annahme, sie behandelt keinen Fehlerfall.

Sie trägt aber nur unter einer Bedingung. Unter `python -O` beziehungsweise
gesetztem `PYTHONOPTIMIZE` werden `assert`-Anweisungen ersatzlos entfernt. Wo eine
solche Anweisung tatsächlich einen Fehlerfall abfinge, liefe die Prüfung dann ins
Leere — deshalb sind die beiden Stellen im heißen Pfad bereits als `raise`
formuliert (siehe tests/unit/test_zusicherungen_ohne_assert.py). Die übrigen sechs
dürfen bleiben, SOLANGE der Schalter nirgends gesetzt wird.

Genau das prüft diese Datei. Ohne sie wäre die Bedingung eine mündliche
Verabredung: Wer `PYTHONOPTIMIZE=1` in eine Betriebskonfiguration schreibt, nähme
sechs Zusicherungen aus dem Code, ohne dass irgendetwas rot würde.

WIE GEPRÜFT WIRD. Nicht am laufenden Testprozess — der läuft ohnehin unoptimiert,
die Aussage wäre wertlos. Geprüft werden die Dateien, die den Betrieb einrichten.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

# Die Dateien, die die Laufzeitumgebung des Betriebs bestimmen. Fehlt eine davon,
# ist das ein Befund und kein Grund zum Überspringen: Der Test soll auffallen,
# wenn die Betriebskonfiguration umzieht.
BETRIEBSDATEIEN = ("Dockerfile", "railway.toml", ".github/workflows/ci.yml")

# Die AUSFÜHRBARE Form, nicht der bloße Name: Eine Suche nach „PYTHONOPTIMIZE"
# fände das Wort auch in dem Kommentar, der erklärt, warum es nicht gesetzt wird.
# Getroffen werden soll die Zuweisung — als Umgebungsvariable oder als Schalter.
_SETZT_OPTIMIERUNG = re.compile(
    r"""(
        PYTHONOPTIMIZE \s* [=:]        # ENV PYTHONOPTIMIZE=1 / PYTHONOPTIMIZE: "1"
        | python \s+ -O                 # python -O / python -OO
        | -m \s+ compileall \s+ -o      # vorkompiliert ohne Zusicherungen
    )""",
    re.VERBOSE | re.IGNORECASE,
)


def _repo_wurzel() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("dateiname", BETRIEBSDATEIEN)
def test_keine_betriebsdatei_schaltet_zusicherungen_ab(dateiname: str) -> None:
    """Keine Datei, die den Betrieb einrichtet, setzt die Optimierung."""
    pfad = _repo_wurzel() / dateiname
    assert pfad.exists(), (
        f"❌ {dateiname} nicht gefunden. Die Betriebskonfiguration ist umgezogen — "
        "dann gehört die Liste BETRIEBSDATEIEN nachgeführt, sonst prüft dieser Test "
        "eine Datei, die niemanden mehr betrifft."
    )

    treffer = _SETZT_OPTIMIERUNG.search(pfad.read_text(encoding="utf-8"))

    assert treffer is None, (
        f"❌ {dateiname} schaltet die Optimierung ein ({treffer.group(0) if treffer else ''}). "
        "Damit fallen alle `assert`-Anweisungen im Quelltext ersatzlos weg — sechs "
        "Zusicherungen verschwinden lautlos. Entweder den Schalter zurücknehmen oder "
        "die betroffenen Stellen vorher auf `raise` umstellen."
    )


def test_der_ausdruck_trifft_auch_wirklich() -> None:
    """Gegenprobe: Der Suchausdruck erkennt die Formen, um die es geht.

    Ohne sie wäre der Test darüber auch dann grün, wenn der Ausdruck gar nichts
    fände — und genau so sieht eine wirkungslose Prüfung aus.
    """
    treffer_soll = [
        "ENV PYTHONOPTIMIZE=1",
        'PYTHONOPTIMIZE: "2"',
        'CMD ["python", "-O", "-m", "foreman"]'.replace('", "', " ")
        .replace('CMD ["', "")
        .replace('"]', ""),
        "python -OO -m uvicorn foreman.main:app",
        "python -m compileall -o 2 src/",
    ]
    for zeile in treffer_soll:
        assert _SETZT_OPTIMIERUNG.search(zeile), f"Nicht erkannt, sollte aber: {zeile!r}"

    treffer_nicht = [
        "# PYTHONOPTIMIZE wird bewusst NICHT gesetzt — sonst fallen die Zusicherungen weg.",
        "ENV PYTHONUNBUFFERED=1",
        "python -m pytest",
    ]
    for zeile in treffer_nicht:
        assert not _SETZT_OPTIMIERUNG.search(zeile), f"Fälschlich erkannt: {zeile!r}"


def test_der_testlauf_selbst_ist_unoptimiert() -> None:
    """Der laufende Prozess führt Zusicherungen aus.

    Für sich genommen sagt das wenig — es hält aber die Suite ehrlich: Liefe sie
    unter `-O`, wäre JEDE `assert`-Zeile in JEDEM Test wirkungslos, und die
    gesamte Prüfung meldete Erfolg, ohne irgendetwas zu prüfen.
    """
    assert sys.flags.optimize == 0, (
        "❌ Die Testsuite läuft unter -O. Damit ist jede Zusicherung in jedem Test "
        "entfernt und der grüne Lauf bedeutungslos."
    )
