# ============================================================
#  FOREMAN — tests/archive/test_fusion.py
#  Zweck: Die quellenübergreifende Fusion der Archiv-Suche (`_fusioniere`).
#  Warum eine eigene Datei: Bis zum 27.08.2026 bekam jeder Treffer genau einen
#         Rang aus genau einer Liste — eine Summierung über Quellen war
#         STRUKTURELL unmöglich, und `RRF_K` war quellenübergreifend ohne jede
#         Wirkung, obwohl GROUND_TRUTH §15.10 es als offene Stellschraube führte.
#         Die Fusion war ein faires Interleaving nach quelleninternem Rang. Seit
#         der Zusammenführung auf den Vorgang ist sie echtes RRF, und damit sind
#         hier Zusicherungen zu halten, die es vorher nicht geben konnte.
#  Herkunft der früheren Fälle: tests/archive/test_substrat_veredelung.py, wo sie
#         gegen `_ohne_doppelfunde` standen. Jede dortige Zusicherung steht hier
#         in ihrer neuen Form wieder — eine davon mit GEÄNDERTEM Ergebnis, siehe
#         `test_zwei_erinnerungen_auf_dieselbe_zeile_werden_ein_vorgang`.
# ============================================================
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from foreman.archive.schemas import ArchiveHit, SourceType
from foreman.archive.search import _fusioniere


def _hit(
    art: str,
    kennung: int,
    *,
    quelle: dict | None = None,
    erinnerung: str | None = None,
    zeit: datetime | None = None,
) -> ArchiveHit:
    """Ein Treffer, wie ihn die Fusion sieht — knapp gehalten."""
    detail: dict[str, Any] = {"herkunft": "gedaechtnis"} if art == "memory" else {}
    if quelle is not None:
        detail["quelle"] = quelle
    if erinnerung is not None:
        detail["erinnerung"] = erinnerung
    return ArchiveHit(
        source_type=art,  # type: ignore[arg-type]
        id=kennung,
        machine_id=1,
        timestamp=zeit or datetime(2026, 6, 6, tzinfo=UTC),
        excerpt="Auszug",
        detail=detail,
    )


def _liste(quelle: SourceType, *treffer: ArchiveHit) -> tuple[SourceType, list[ArchiveHit]]:
    return (quelle, list(treffer))


def _kennungen(treffer: list[ArchiveHit]) -> list[tuple[str, int]]:
    return [(h.source_type, h.id) for h in treffer]


# ──────────────────────────────────────────────────────────────────────
#  Ein Vorgang steht einmal da — was vorher Entfernen war, ist jetzt Verrechnen
# ──────────────────────────────────────────────────────────────────────


def test_derselbe_vorgang_aus_zwei_quellen_steht_einmal_da() -> None:
    """Dasselbe Ereignis, zwei Ranglisten — aber ein Vorgang.

    Eine Schichtnotiz ist über ihr Embedding als `note` auffindbar und über ihre
    Spiegelung als `memory`. Ungefiltert rangierte die Fusion denselben Vorgang
    doppelt: Er verdrängte andere Treffer, ohne mehr zu sagen.
    """
    ergebnis = _fusioniere(
        [
            _liste("note", _hit("note", 7)),
            _liste("alarm", _hit("alarm", 3)),
            _liste("memory", _hit("memory", 0, quelle={"art": "note", "id": 7})),
        ],
        k=10,
    )

    assert _kennungen(ergebnis) == [("note", 7), ("alarm", 3)]


def test_der_zusammengefuehrte_vorgang_traegt_beide_herkuenfte() -> None:
    """Die Einigkeit muss SICHTBAR sein, nicht nur wirksam.

    Vorher wurde die Erinnerung weggeworfen — genau in dem Augenblick, in dem
    zwei Quellen sich einig waren, verschwand die Einigkeit. Jetzt hebt sie den
    Treffer; ohne `gefunden_von` sähe das Ergebnis aber aus wie ein Einzelfund,
    und dem Werker fehlte die Auskunft, dass das Gedächtnis denselben Vorgang
    kennt.
    """
    ergebnis = _fusioniere(
        [
            _liste("note", _hit("note", 7)),
            _liste("memory", _hit("memory", 0, quelle={"art": "note", "id": 7})),
        ],
        k=10,
    )

    assert len(ergebnis) == 1
    assert ergebnis[0].source_type == "note"
    assert ergebnis[0].gefunden_von == ["note", "memory"]


def test_der_eigene_treffer_wird_vertreter_nicht_die_erinnerung() -> None:
    """Er ist die Quelle, sie die Ableitung.

    AUFBAU-KONTROLLE zur Zusammenführung: Ohne diese Zusicherung bliebe offen,
    WELCHER der beiden ausgeliefert wird. Der eigene Treffer trägt die echte
    Kennung, seine Zeitangabe stammt aus der Datenbank statt aus dem Abruf, und
    sein Auszug ist der ungekürzte Originaltext — er ist der belastbarere. Die
    Erinnerung steht hier bewusst auf dem BESSEREN Rang und darf ihn trotzdem
    nicht vertreten.
    """
    ergebnis = _fusioniere(
        [
            _liste("memory", _hit("memory", 0, quelle={"art": "maintenance", "id": 2})),
            _liste("maintenance", _hit("maintenance", 99), _hit("maintenance", 2)),
        ],
        k=10,
    )

    zusammengefuehrt = [h for h in ergebnis if h.id == 2]
    assert len(zusammengefuehrt) == 1
    assert zusammengefuehrt[0].source_type == "maintenance"
    assert set(zusammengefuehrt[0].gefunden_von) == {"memory", "maintenance"}


# ──────────────────────────────────────────────────────────────────────
#  Der Zusatznutzen des Gedächtnisses — er darf durch die Rückabbildung
#  nicht verschwinden
# ──────────────────────────────────────────────────────────────────────


def test_erinnerung_ohne_rueckweg_bleibt_eigenstaendig() -> None:
    """Altbestand trägt den Rückweg nicht — dann wird NICHT geraten.

    Sie könnte auf denselben Vorgang zeigen oder auf einen anderen; das ist nicht
    entscheidbar. Eine geratene Zusammenführung nähme dem Werker einen Treffer,
    den niemand geprüft hat.
    """
    ergebnis = _fusioniere(
        [_liste("note", _hit("note", 7)), _liste("memory", _hit("memory", 0))],
        k=10,
    )

    assert len(ergebnis) == 2


def test_erinnerung_auf_eine_nicht_gelistete_zeile_bleibt_eigenstaendig() -> None:
    """Der eigentliche Gewinn der vierten Quelle darf nicht wegfallen.

    Zeigt eine Erinnerung auf einen Vorgang, den keine eigene Quelle gefunden
    hat, ist sie der einzige Weg dorthin — genau der Fall, in dem die deutsche
    Volltextsuche an Wortzusammensetzungen scheitert und Wartung/Alarm ohne
    Vektorzweig nichts liefern.
    """
    ergebnis = _fusioniere(
        [
            _liste("note", _hit("note", 7)),
            _liste("memory", _hit("memory", 0, quelle={"art": "maintenance", "id": 2})),
        ],
        k=10,
    )

    assert len(ergebnis) == 2
    eigenstaendig = [h for h in ergebnis if h.source_type == "memory"]
    assert len(eigenstaendig) == 1
    assert eigenstaendig[0].gefunden_von == ["memory"]


def test_abgeleitete_einsichten_bleiben_immer_eigenstaendig() -> None:
    """Drift, Ereigniskette und Werker-Empfehlung tragen NIE eine Quellzeile.

    Sie sind im Schreibpfad fest auf `source_id: None` gesetzt (reasoners/*),
    weil sie aus mehreren Zeilen entstehen und auf keine einzelne zeigen. Genau
    diese Treffer sind das, was das Gedächtnis WEISS und das Archiv nicht — sie
    dürfen durch die Rückabbildung nicht zu Anhängseln eigener Treffer werden.
    Zwei verschiedene solche Einsichten müssen zwei Treffer bleiben.
    """
    ergebnis = _fusioniere(
        [
            _liste(
                "memory",
                _hit("memory", 0, erinnerung="mem-a"),
                _hit("memory", 0, erinnerung="mem-b"),
            )
        ],
        k=10,
    )

    assert len(ergebnis) == 2


def test_zwei_rueckweglose_erinnerungen_ohne_kennung_fallen_nicht_zusammen() -> None:
    """DIE FALLE der Zusammenführung, und der Grund für den dritten Schlüssel-Zweig.

    Eine Erinnerung trägt `source_type="memory"` und fest `id=0`. Über
    `(source_type, id)` fielen ALLE rückweglosen Erinnerungen auf denselben
    Schlüssel zusammen: aus drei verschiedenen Treffern würde ein einziger
    Phantom-Treffer mit der Summe ihrer Punkte — und zwei Vorgänge verschwänden
    aus der Liste, ohne dass irgendetwas auffiele.
    """
    ergebnis = _fusioniere(
        [_liste("memory", _hit("memory", 0), _hit("memory", 0), _hit("memory", 0))],
        k=10,
    )

    assert len(ergebnis) == 3


def test_dieselbe_erinnerung_zweimal_geliefert_belegt_einen_platz() -> None:
    """Die Substrat-Kennung ist der Schlüssel, wenn der Rückweg fehlt.

    Der Abruf kann denselben Eintrag zweimal zurückgeben. Ohne diesen Zweig
    bekäme er zwei verschiedene Ersatzschlüssel (`memory#1`, `memory#2`), stünde
    zweimal in der Liste und bekäme die doppelte Punktzahl — für eine einzige
    Erinnerung.

    Belegt daran, dass die Testvorlage in `test_substrat_veredelung.py` bis zum
    27.08.2026 zwei angeblich verschiedene Erinnerungen mit DERSELBEN Kennung
    prägte: Solange nichts zusammengeführt wurde, fiel das niemandem auf.
    """
    ergebnis = _fusioniere(
        [
            _liste(
                "memory",
                _hit("memory", 0, erinnerung="mem-a"),
                _hit("memory", 0, erinnerung="mem-a"),
            )
        ],
        k=10,
    )

    assert len(ergebnis) == 1


def test_zwei_erinnerungen_auf_dieselbe_zeile_werden_ein_vorgang() -> None:
    """GEÄNDERTES VERHALTEN gegenüber `_ohne_doppelfunde` (27.08.2026).

    Vorher blieben beide stehen: Die Entdoppelung griff nur gegen eigene Treffer,
    nicht zwischen Erinnerungen — der Fall war dort ausdrücklich offen gelassen,
    und `werte_aus.py` musste ihn beim Messen nachträglich herausrechnen, damit
    die Trefferquote nicht über 1,0 steigt.

    Jetzt entscheidet der Vorgang, nicht die Herkunft: Zwei Erinnerungen auf
    `maintenance:2` sind ein Vorgang und belegen einen Platz. Sie bekommen dabei
    NICHT die doppelte Punktzahl — innerhalb einer Rangliste zählt nur der beste
    Rang, denn zweimal dieselbe Quelle ist keine zweite Meinung.
    """
    ergebnis = _fusioniere(
        [
            _liste(
                "memory",
                _hit("memory", 0, quelle={"art": "maintenance", "id": 2}),
                _hit("memory", 0, quelle={"art": "maintenance", "id": 2}),
            )
        ],
        k=10,
    )

    assert len(ergebnis) == 1
    assert ergebnis[0].gefunden_von == ["memory"]


def test_eine_quelle_hebt_einen_vorgang_nicht_durch_wiederholung() -> None:
    """AUFBAU-KONTROLLE zum vorigen Fall: die Wiederholung darf nicht heben.

    Ohne diese Zusicherung liesse sich die Zusammenführung so bauen, dass sie die
    Punkte doch addiert — eine Quelle, die denselben Vorgang zweimal liefert,
    schöbe ihn dann an jedem einzeln gefundenen vorbei. Der wiederholte Vorgang
    steht hier auf den Rängen 1 und 2, der Vergleichstreffer allein auf Rang 1;
    bei Addition (1/61 + 1/62) läge er vorn, bei bestem Rang (1/61) gleichauf —
    und der Zeitstempel entscheidet dann zugunsten des jüngeren.
    """
    frueher = datetime(2026, 6, 1, tzinfo=UTC)
    spaeter = datetime(2026, 6, 9, tzinfo=UTC)
    ergebnis = _fusioniere(
        [
            _liste(
                "memory",
                _hit("memory", 0, quelle={"art": "maintenance", "id": 2}, zeit=frueher),
                _hit("memory", 0, quelle={"art": "maintenance", "id": 2}, zeit=frueher),
            ),
            _liste("alarm", _hit("alarm", 3, zeit=spaeter)),
        ],
        k=10,
    )

    assert _kennungen(ergebnis)[0] == ("alarm", 3)


# ──────────────────────────────────────────────────────────────────────
#  Einigkeit schlägt Spitzenrang — der Chorus-Effekt, vorher unmöglich
# ──────────────────────────────────────────────────────────────────────


def _chorus_listen() -> list[tuple[SourceType, list[ArchiveHit]]]:
    """Der Aufbau für den Chorus-Fall: `note:7` steht in ZWEI Listen auf Rang 5,
    `alarm:3` allein auf Rang 1."""
    return [
        _liste("note", *[_hit("note", 100 + i) for i in range(4)], _hit("note", 7)),
        _liste("alarm", _hit("alarm", 3)),
        _liste(
            "memory",
            *[_hit("memory", 0, erinnerung=f"m{i}") for i in range(4)],
            _hit("memory", 0, quelle={"art": "note", "id": 7}),
        ),
    ]


def test_zwei_quellen_die_sich_einig_sind_schlagen_einen_spitzentreffer() -> None:
    """Der Grund für den ganzen Umbau.

    Ein Vorgang, den zwei Quellen unabhängig finden, ist wahrscheinlicher
    zutreffend als einer, den nur eine findet (Authority Effect, Spoerri 2007).
    Vorher war das nicht ausdrückbar: Jeder Treffer trug genau einen Rang aus
    genau einer Liste, und der beste Einzelrang gewann immer.

    Hier steht der bestätigte Vorgang in BEIDEN Listen nur auf Rang 5
    (zweimal 1/65 = 0,0308), der Einzelfund auf Rang 1 (1/61 = 0,0164).
    """
    assert _kennungen(_fusioniere(_chorus_listen(), k=10))[0] == ("note", 7)


def test_ein_spitzentreffer_schlaegt_einen_einzelnen_zweitplatzierten() -> None:
    """AUFBAU-KONTROLLE zum Chorus: ohne Einigkeit gilt weiter der Rang.

    Ohne diesen Zwilling wäre eine Fusion, die IMMER Erinnerungen nach hinten
    (oder nach vorn) sortiert, von einer wirksamen nicht zu unterscheiden. Eine
    Erinnerung auf Rang 1 steht vor einem eigenen Treffer auf Rang 2 — das war
    schon vorher so (Verdrängung, C-079) und bleibt richtig.

    Der Zeitstempel von `note:99` ist bewusst der jüngere: Beide stehen auf Rang 1
    ihrer Liste und haben damit denselben Punktestand. Ohne diesen Unterschied
    entschiede der Tiebreaker über den Quelltyp — alphabetisch, also zufällig in
    der Sache. Der Fall gehört geprüft, aber nicht hier.
    """
    ergebnis = _fusioniere(
        [
            _liste(
                "note",
                _hit("note", 99, zeit=datetime(2026, 6, 9, tzinfo=UTC)),
                _hit("note", 5),
            ),
            _liste("memory", _hit("memory", 0, erinnerung="m1")),
        ],
        k=10,
    )

    assert _kennungen(ergebnis) == [("note", 99), ("memory", 0), ("note", 5)]


# ──────────────────────────────────────────────────────────────────────
#  Die Stellschraube muss wirken — sonst gehört sie nicht in die Liste
# ──────────────────────────────────────────────────────────────────────


def test_die_rrf_konstante_aendert_die_reihenfolge(monkeypatch: pytest.MonkeyPatch) -> None:
    """`RRF_K` ist seit dem Umbau quellenübergreifend WIRKSAM — und deshalb erst
    jetzt eine Stellschraube.

    GROUND_TRUTH §15.10 führte sie als "nie kalibriert" auf, während sie in der
    quellenübergreifenden Fusion gar keine Wirkung HATTE: ohne Summierung fällt
    `1/(k+r)` in r streng monoton, jedes k liefert dieselbe Reihenfolge. Eine
    Zahl, die man kalibrieren wollte, ohne dass ein Lauf mit zwei Werten zwei
    Ergebnisse liefert, ist keine Stellschraube, sondern eine Konstante.

    Die Rechnung: Ein von zwei Quellen auf Rang r bestätigter Vorgang schlägt
    einen Einzelfund auf Rang 1, sobald `2/(k+r) > 1/(k+1)`, also `k > r-2`. Bei
    r = 5 heisst das: k = 60 → Einigkeit gewinnt, k = 1 → Spitzenrang gewinnt.
    Kleines k gewichtet Spitzenränge, grosses k gewichtet Einigkeit.
    """
    monkeypatch.setattr("foreman.archive.search.RRF_K", 60)
    mit_sechzig = _kennungen(_fusioniere(_chorus_listen(), k=10))

    monkeypatch.setattr("foreman.archive.search.RRF_K", 1)
    mit_eins = _kennungen(_fusioniere(_chorus_listen(), k=10))

    assert mit_sechzig[0] == ("note", 7), "bei k=60 muss Einigkeit den Spitzenrang schlagen"
    assert mit_eins[0] == ("alarm", 3), "bei k=1 muss der Spitzenrang die Einigkeit schlagen"


# ──────────────────────────────────────────────────────────────────────
#  Form und Grenzen
# ──────────────────────────────────────────────────────────────────────


def test_jeder_ausgelieferte_treffer_nennt_seine_quellen() -> None:
    """Ein leeres `gefunden_von` wäre ein Treffer, den niemand gefunden hat.

    Das Feld hat einen leeren Vorgabewert, damit die Treffer-Fabriken
    (`_note_hit` & Co.) es nicht einzeln setzen müssen. Genau deshalb braucht es
    hier die Zusicherung: Ein Zweig, der die Zusammenführung umgeht, lieferte
    sonst stillschweigend Treffer ohne Herkunftsangabe aus.
    """
    ergebnis = _fusioniere(
        [
            _liste("note", _hit("note", 7), _hit("note", 8)),
            _liste("maintenance", _hit("maintenance", 2)),
            _liste("memory", _hit("memory", 0, erinnerung="m1")),
        ],
        k=10,
    )

    assert len(ergebnis) == 4
    assert all(h.gefunden_von for h in ergebnis)


def test_die_ausgabe_wird_erst_nach_dem_zusammenfuehren_gekuerzt() -> None:
    """Sonst hinterliesse jeder zusammengeführte Vorgang eine Lücke.

    Würde vor dem Zusammenführen auf k geschnitten, verlöre die Liste bei jedem
    Doppelfund einen Platz — der Werker sähe neun Treffer, wo zehn zu vergeben
    waren, und niemand könnte es ihm ansehen.
    """
    ergebnis = _fusioniere(
        [
            _liste("note", _hit("note", 7), _hit("note", 8), _hit("note", 9)),
            _liste("memory", _hit("memory", 0, quelle={"art": "note", "id": 7})),
        ],
        k=3,
    )

    assert len(ergebnis) == 3


def test_leere_quellen_ergeben_ein_leeres_ergebnis() -> None:
    """Kein Treffer ist kein Fehler — die Suche darf dann nichts erfinden."""
    assert _fusioniere([_liste("note"), _liste("memory")], k=10) == []
