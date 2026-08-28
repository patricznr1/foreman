# ══════════════════════════════════════════════════════════════
# FOREMAN — Das Abbild lädt GENAU das Modell, das die Konfiguration wählt
# Der Modellname steht an zwei Stellen. Diese Datei hält sie zusammen.
# ══════════════════════════════════════════════════════════════
"""Bindet den Modellnamen im Dockerfile an `EmbeddingSettings.st_model`.

WORUM ES GEHT. Das Einbettungs-Modell wird beim Bau ins Abbild geladen, damit zur
Laufzeit nichts nachgeladen werden muss. Der Name steht dafür WÖRTLICH im
Dockerfile — nicht aus Bequemlichkeit, sondern damit die Schicht
zwischenspeicherbar bleibt: Läse der Bauschritt den Namen aus dem Quelltext, müsste
er nach jeder Code-Änderung neu laufen und 2,3 GB erneut laden.

Der Preis dafür ist eine zweite Wahrheit. Wer `st_model` in der Konfiguration
ändert und das Dockerfile vergisst, bekommt ein Abbild, in dem das FALSCHE Modell
liegt — und das ist der teuerste Fall, weil er nicht knallt: Die Bibliothek findet
das gewählte Modell nicht im Zwischenspeicher, versucht es zu laden, scheitert am
fehlenden Netz oder an den Rechten, und `embed_and_search_hybrid` fängt den Fehler
ab und sucht ab da still nur noch im Volltext weiter. Die Suche liefert weiterhin
Treffer. Sie sind nur nicht mehr semantisch.

WIE GEPRÜFT WIRD. Am ausführbaren Text des Bauschritts, nicht am Vorkommen des
Namens irgendwo in der Datei — der Name steht auch in den Kommentaren, die
erklären, warum er dort steht. Getroffen werden soll der Aufruf.
"""

from __future__ import annotations

import re
from pathlib import Path

from foreman.embeddings.config import EmbeddingSettings

# Der Aufruf im Bauschritt, nicht der bloße Name: `SentenceTransformer('…')`.
# Ohne die Klammer und den Bezeichner träfe der Ausdruck auch die Kommentarzeile,
# die den Modellnamen bloß nennt — und der Test bliebe grün, während der
# tatsächliche Aufruf ein anderes Modell lädt.
_LADEAUFRUF = re.compile(r"""SentenceTransformer\(\s*['"]([^'"]+)['"]""")


def _dockerfile() -> Path:
    return Path(__file__).resolve().parents[2] / "Dockerfile"


def test_das_dockerfile_laedt_das_konfigurierte_modell() -> None:
    """Der Bauschritt lädt genau das Modell, das `st_model` vorgibt."""
    pfad = _dockerfile()
    assert pfad.exists(), (
        "❌ Dockerfile nicht gefunden. Zieht die Betriebskonfiguration um, gehört "
        "dieser Test nachgeführt — sonst prüft er eine Datei, die es nicht gibt."
    )

    treffer = _LADEAUFRUF.findall(pfad.read_text(encoding="utf-8"))

    assert treffer, (
        "❌ Das Dockerfile lädt kein Einbettungs-Modell mehr. Damit lädt es der "
        "erste Suchaufruf zur Laufzeit nach — und scheitert das, degradiert die "
        "Archiv-Suche STILL auf Volltext. Entweder den Bauschritt "
        "wiederherstellen oder diesen Test mit Begründung entfernen."
    )

    erwartet = EmbeddingSettings().st_model
    # JEDE Fundstelle einzeln, nicht die Anzahl: Ein Zähler bliebe grün, solange
    # irgendwo noch der richtige Name steht — auch wenn daneben ein falscher lädt.
    for gefunden in treffer:
        assert gefunden == erwartet, (
            f"❌ Das Dockerfile lädt '{gefunden}', die Konfiguration wählt "
            f"'{erwartet}'. Das Abbild enthielte dann ein Modell, das niemand "
            "benutzt, und das benutzte fehlte. Beide Stellen zusammen ändern."
        )


def test_der_ausdruck_trifft_den_aufruf_und_nicht_den_kommentar() -> None:
    """Gegenprobe: Ohne sie wäre der Test oben auch dann grün, wenn er nichts fände.

    Der Modellname steht im Dockerfile mehrfach — im Aufruf UND in den Kommentaren,
    die begründen, warum er dort steht. Genau diese Verwechslung soll der Ausdruck
    nicht machen.
    """
    trifft = [
        "SentenceTransformer('Snowflake/snowflake-arctic-embed-l-v2.0', device='cpu')",
        'SentenceTransformer("BAAI/bge-m3")',
        "SentenceTransformer(  'x/y'  )",
    ]
    for zeile in trifft:
        assert _LADEAUFRUF.search(zeile), f"Nicht erkannt, sollte aber: {zeile!r}"

    trifft_nicht = [
        "#     SNOWFLAKE ARCTIC v2.0 statt bge-m3 — Begründung siehe config.py",
        "#     Der Modellname 'Snowflake/snowflake-arctic-embed-l-v2.0' steht wörtlich hier.",
        "st_model: str = 'Snowflake/snowflake-arctic-embed-l-v2.0'",
    ]
    for zeile in trifft_nicht:
        assert not _LADEAUFRUF.search(zeile), f"Fälschlich erkannt: {zeile!r}"


def test_der_zwischenspeicher_wird_gesetzt_und_gehoert_dem_dienstnutzer() -> None:
    """HF_HOME zeigt ins Abbild, und der Nutzer darf dort schreiben.

    Zwei getrennte Zusicherungen, die zusammen tragen. Fehlt die Variable, sucht
    die Bibliothek den Zwischenspeicher woanders und findet das eingebackene
    Modell nicht. Fehlt der Eigentumswechsel, findet sie es zwar, kann aber ihre
    Sperrdateien nicht anlegen — der Dienst läuft als nicht-privilegierter Nutzer.
    """
    text = _dockerfile().read_text(encoding="utf-8")

    assert re.search(r"^ENV\s+HF_HOME=/opt/hf-cache\s*$", text, re.MULTILINE), (
        "❌ Keine ENV-Zeile setzt HF_HOME auf /opt/hf-cache. Ohne sie sucht die "
        "Bibliothek den Zwischenspeicher an ihrem Vorgabeort und lädt das Modell "
        "erneut — falls sie darf."
    )
    assert "chown -R foreman:foreman /opt/hf-cache" in text, (
        "❌ Der Zwischenspeicher wechselt nicht in das Eigentum des Dienstnutzers. "
        "Der Dienst läuft unter uid 10001 und könnte dort nicht schreiben."
    )
