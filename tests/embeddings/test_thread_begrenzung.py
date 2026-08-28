# ============================================================
#  FOREMAN — tests/embeddings/test_thread_begrenzung.py
#  Zweck: Hält die Threadbegrenzung des lokalen Einbettungspfads fest.
#  Warum das eine eigene Datei wert ist: Der Fehler, gegen den sie gebaut ist,
#         wirft nicht. Er macht die Suche nur langsam — gemessen am 28.08.2026
#         5,505 s statt 0,154 s je Anfrage, Faktor 36. Eine langsame Suche meldet
#         nichts; sie sieht aus wie „das dauert eben". Gefunden wurde es nur,
#         weil ein zweites System dieselbe Aufgabe schneller löste (C-095).
# ============================================================
from __future__ import annotations

from pathlib import Path

import pytest

from foreman.embeddings import backends
from foreman.embeddings.backends import (
    _THREAD_OBERGRENZE,
    _ziel_threadzahl,
    _zugeteilte_kerne,
)


def _cgroup(monkeypatch: pytest.MonkeyPatch, inhalte: dict[str, str]) -> None:
    """Stellt die cgroup-Dateien nach — ohne echte Dateien im Testlauf."""
    echt = Path.read_text

    def lies(self: Path, *a: object, **k: object) -> str:
        # `as_posix()` statt `str()`: Unter Windows normalisiert WindowsPath die
        # Trennzeichen zu Backslashes, und der Vergleich gegen den Linux-Pfad
        # ginge still ins Leere — der Test wäre grün, ohne etwas zu stellen.
        pfad = self.as_posix()
        if pfad in inhalte:
            return inhalte[pfad]
        if pfad.startswith("/sys/fs/cgroup"):
            raise OSError("nicht vorhanden")
        return echt(self, *a, **k)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "read_text", lies)


# ──────────────────────────────────────────────────────────────────────
#  Die Zuteilung — was der Behälter WIRKLICH hergibt
# ──────────────────────────────────────────────────────────────────────


def test_die_quote_des_behaelters_schlaegt_die_kerne_des_wirts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DER FALL, UM DEN ES GEHT.

    Auf der Betriebsmaschine meldet `os.cpu_count()` 48 (Wirt), während der
    Behälter 24 zugeteilt bekommt. Wer den Wirt fragt, überzieht um das Doppelte
    — und bezahlt das nicht mit Überlastung, sondern mit Abstimmung zwischen
    Threads, die es gar nicht gibt.
    """
    _cgroup(monkeypatch, {"/sys/fs/cgroup/cpu.max": "2400000 100000\n"})
    monkeypatch.setattr(backends.os, "cpu_count", lambda: 48)

    assert _zugeteilte_kerne() == 24


def test_ohne_quote_zaehlt_die_affinitaet_oder_die_kernzahl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`max` heisst „keine Quote" — dann trägt die nächste Quelle.

    AUFBAU-KONTROLLE zugleich: Ohne diesen Fall liesse sich die Quotenlesung
    kaputtmachen, ohne dass etwas rot würde — der Test darüber prüft nur den
    Pfad MIT Quote.
    """
    _cgroup(monkeypatch, {"/sys/fs/cgroup/cpu.max": "max 100000\n"})
    monkeypatch.delattr(backends.os, "sched_getaffinity", raising=False)
    monkeypatch.setattr(backends.os, "cpu_count", lambda: 8)

    assert _zugeteilte_kerne() == 8


def test_die_alte_cgroup_form_wird_auch_gelesen(monkeypatch: pytest.MonkeyPatch) -> None:
    """cgroup v1 führt Quote und Periode in ZWEI Dateien.

    Ohne diesen Zweig fiele ein Behälter der ersten Generation stillschweigend
    auf die Kerne des Wirts zurück — also genau in den Fehler.
    """
    _cgroup(
        monkeypatch,
        {
            "/sys/fs/cgroup/cpu/cpu.cfs_quota_us": "400000\n",
            "/sys/fs/cgroup/cpu/cpu.cfs_period_us": "100000\n",
        },
    )
    monkeypatch.setattr(backends.os, "cpu_count", lambda: 48)

    assert _zugeteilte_kerne() == 4


def test_unlesbare_quelle_faellt_nicht_auf_den_wirt_zurueck(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ist gar nichts lesbar, bleibt die Kernzahl — aber nie ein Wert unter 1."""
    _cgroup(monkeypatch, {})
    monkeypatch.delattr(backends.os, "sched_getaffinity", raising=False)
    monkeypatch.setattr(backends.os, "cpu_count", lambda: None)

    assert _zugeteilte_kerne() == 1


# ──────────────────────────────────────────────────────────────────────
#  Die Obergrenze — sie deckelt nach oben UND unten
# ──────────────────────────────────────────────────────────────────────


def test_die_obergrenze_greift_auf_einem_grossen_behaelter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Viel Zuteilung heisst nicht viele Threads.

    Gemessen: 16 Threads 0,082 s, 24 Threads 0,193 s, 48 Threads 5,340 s. Mehr
    Threads sind ab hier langsamer, nicht schneller — die Grenze ist kein
    Sparzwang, sondern der gemessene Umschlagpunkt.
    """
    monkeypatch.setattr(backends, "_zugeteilte_kerne", lambda: 64)

    assert _ziel_threadzahl() == _THREAD_OBERGRENZE


def test_auf_einem_kleinen_behaelter_gilt_die_zuteilung(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AUFBAU-KONTROLLE zur Obergrenze: Sie darf nicht zur festen Zahl werden.

    Ohne diesen Zwilling liesse sich die Deckelung durch eine Konstante ersetzen
    — und ein Behälter mit zwei Kernen startete 16 Threads, also wieder das
    Ausgangsproblem, nur kleiner.
    """
    monkeypatch.setattr(backends, "_zugeteilte_kerne", lambda: 2)

    assert _ziel_threadzahl() == 2


def test_die_zielzahl_ist_nie_null(monkeypatch: pytest.MonkeyPatch) -> None:
    """Null Threads wäre kein sparsamer Betrieb, sondern ein Absturz beim Laden."""
    monkeypatch.setattr(backends, "_zugeteilte_kerne", lambda: 0)

    assert _ziel_threadzahl() == 1


# ──────────────────────────────────────────────────────────────────────
#  Die Begrenzung darf nichts kaputtmachen
# ──────────────────────────────────────────────────────────────────────


def test_ohne_torch_passiert_nichts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Eine Geschwindigkeitsfrage darf den Einbettungspfad nicht zum Scheitern bringen.

    Belegt am 28.08.2026: Die erste Fassung importierte torch ohne Absicherung.
    Damit riss sie jeden Pfad mit, der ein Ersatzmodell einspielt und die schwere
    Bibliothek gar nicht braucht — der Aufruf endete in `ProviderUnavailable`,
    also in einer stillen Degradierung der Suche auf Volltext. Aus einer
    Optimierung wäre ein Ausfall geworden.

    Fehlt torch wirklich, scheitert das Laden des Modells unmittelbar danach von
    selbst; hier ist nichts zu verbergen.
    """
    import builtins

    echt = builtins.__import__

    def ohne_torch(name: str, *a: object, **k: object) -> object:
        if name == "torch":
            raise ImportError("torch ist hier nicht vorhanden")
        return echt(name, *a, **k)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", ohne_torch)

    backends._begrenze_threads()  # darf nicht werfen
