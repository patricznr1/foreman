# ============================================================
#  FOREMAN — tests/unit/test_substrate_content.py
#  Zweck: Pflicht-Test-Block für die Formulierung gespiegelter Ereignisse
#         (substrate/content.py). Prüft die Freitext-Erweiterung von Alarm und
#         Wartung (24.08.2026) und — wichtiger — dass der Altbestand ohne diese
#         Felder WEITERHIN einen Satz bekommt statt übersprungen zu werden.
#  Architektur-Einordnung: Quality Gate §10.3, Vertrag der Substrat-Brücke §12.4.
# ============================================================
from __future__ import annotations

import pytest

from foreman.substrate.content import CONTENT_BUILDERS, _gegenstand, baue_inhalt

# Nutzlast einer ALTEN Zeile: genau die Felder, die vor dem 24.08.2026
# geschrieben wurden. Diese Gestalt liegt real in der Datenbank und ist der
# einzige Grund für den weichen Feldzugriff.
ALT_ALARM = {
    "source_type": "alarm",
    "source_id": 5,
    "code": "TOOL_LOAD_HIGH",
    "severity": "warning",
    "category": "hardware",
    "machine_id": 8,
    "raised_at": "2026-06-19T14:00:00+00:00",
}
ALT_WARTUNG = {
    "source_type": "maintenance",
    "source_id": 11,
    "type": "tool_change",
    "machine_id": 8,
    "component_id": 3,
    "performed_at": "2026-06-04T09:00:00+00:00",
    "performed_by": "hmac:abc123",
}


# ──────────────────────────────────────────────────────────────────────
#  Der Altbestand darf nicht ausfallen
# ──────────────────────────────────────────────────────────────────────


def test_alarm_ohne_meldung_ergibt_den_bisherigen_satz_wortgleich() -> None:
    """Die Zusicherung aus dem Docstring von `_alarm_raised`, eingefordert.

    Der weiche Zugriff ist der ganze Grund, warum der Altbestand die Erweiterung
    überlebt. Wäre er hart, würfe `baue_inhalt` einen KeyError, der Nachtrag
    übersprünge die Zeile — und aus dem Gedächtnis verschwänden alle Alarme, die
    vor dem 24.08.2026 entstanden sind. Der Satz muss deshalb WORTGLEICH zur
    bisherigen Fassung sein, nicht nur „ähnlich": Ein angehängtes Leerzeichen
    genügt schon, damit der Inhalts-Hash der Gegenstelle einen zweiten Eintrag
    für dasselbe Ereignis anlegt.
    """
    assert baue_inhalt("alarm_raised", ALT_ALARM) == (
        "Alarm 5 TOOL_LOAD_HIGH (warning/hardware) an Maschine 8 ausgelöst "
        "(2026-06-19T14:00:00+00:00)."
    )


def test_wartung_ohne_beschreibung_ergibt_den_bisherigen_satz_wortgleich() -> None:
    assert baue_inhalt("maintenance_performed", ALT_WARTUNG) == (
        "Wartung 11 (tool_change) an Maschine 8 durchgeführt (2026-06-04T09:00:00+00:00)."
    )


@pytest.mark.parametrize("leerwert", [None, "", "   ", "\n\t "])
def test_leerer_freitext_haengt_nichts_an(leerwert: object) -> None:
    """`None`, leer und reiner Weissraum sind gleich zu behandeln.

    Ohne diese Gleichbehandlung entstünde für eine Zeile mit leerer Beschreibung
    ein Satz mit angehängtem Leerzeichen — verschieden vom Satz derselben Zeile
    ohne das Feld, obwohl beide dasselbe bedeuten. Zwei Sätze für einen
    Sachverhalt heisst: zwei Erinnerungen für ein Ereignis.
    """
    ohne_feld = baue_inhalt("maintenance_performed", ALT_WARTUNG)
    mit_leerem_feld = baue_inhalt("maintenance_performed", {**ALT_WARTUNG, "description": leerwert})
    assert mit_leerem_feld == ohne_feld

    alarm_ohne = baue_inhalt("alarm_raised", ALT_ALARM)
    alarm_leer = baue_inhalt("alarm_raised", {**ALT_ALARM, "message": leerwert})
    assert alarm_leer == alarm_ohne


def test_nicht_zeichenkette_wird_ignoriert_statt_eingebaut() -> None:
    """Ein Nicht-Text im Feld darf keinen `str()`-Abdruck in den Satz schreiben.

    Aufbau-Kontrolle zur Gleichbehandlung oben: Ohne diesen Fall bliebe offen, ob
    `_freitext` wirklich auf den Typ prüft oder nur auf Wahrheitswert — eine
    Liste mit Inhalt ist wahr und landete sonst als "['a']" im Gedächtnis.
    """
    ohne_feld = baue_inhalt("maintenance_performed", ALT_WARTUNG)
    for unfug in (42, ["a"], {"x": 1}, object()):
        assert baue_inhalt("maintenance_performed", {**ALT_WARTUNG, "description": unfug}) == (
            ohne_feld
        )


# ──────────────────────────────────────────────────────────────────────
#  Der Freitext kommt an
# ──────────────────────────────────────────────────────────────────────


def test_wartung_traegt_die_beschreibung() -> None:
    """Der eigentliche Zweck der Erweiterung.

    Der Grund eines Degradationsverlaufs steht ausschliesslich hier (§12.5,
    Beobachtungsgrenze). Geprüft wird der VOLLSTÄNDIGE Satz, nicht nur ein
    Vorkommen — ein `in`-Test bliebe grün, wenn die Beschreibung an falscher
    Stelle oder doppelt landete.
    """
    beschreibung = (
        "Werkzeugwechsel Fügepresse 2: Fügestempel getauscht. Wechselintervall "
        "faktisch 90 Tage statt der vorgesehenen 30 — bewusst gestreckt."
    )
    assert baue_inhalt("maintenance_performed", {**ALT_WARTUNG, "description": beschreibung}) == (
        "Wartung 11 (tool_change) an Maschine 8 durchgeführt (2026-06-04T09:00:00+00:00). "
        f"{beschreibung}"
    )


def test_alarm_traegt_die_meldung() -> None:
    meldung = "PR-02 Fügekraft über Erwartung — Werkzeugverschleiss vermutet"
    assert baue_inhalt("alarm_raised", {**ALT_ALARM, "message": meldung}) == (
        "Alarm 5 TOOL_LOAD_HIGH (warning/hardware) an Maschine 8 ausgelöst "
        f"(2026-06-19T14:00:00+00:00). {meldung}"
    )


def test_freitext_wird_von_umgebendem_weissraum_befreit() -> None:
    """Sonst entstünde für denselben Sachverhalt je nach Quelle ein anderer Satz."""
    with_raum = baue_inhalt("alarm_raised", {**ALT_ALARM, "message": "  Leckage vermutet \n"})
    ohne_raum = baue_inhalt("alarm_raised", {**ALT_ALARM, "message": "Leckage vermutet"})
    assert with_raum == ohne_raum
    assert with_raum.endswith("Leckage vermutet")


# ──────────────────────────────────────────────────────────────────────
#  Die Invariante des Moduls bleibt gewahrt
# ──────────────────────────────────────────────────────────────────────


def test_pflichtfelder_werfen_weiterhin() -> None:
    """Die Erweiterung darf die harte Prüfung der Pflichtfelder nicht aufweichen.

    Gegenprobe zum weichen Zugriff: Weich ist NUR der Freitext. Fehlt ein Feld,
    das den Sachverhalt trägt, ist die Zeile defekt und soll auffallen — auf dem
    Schreibweg als Programmierfehler, im Nachtrag als übersprungene Zeile.
    Ohne diesen Test liesse sich der weiche Zugriff später versehentlich auf
    Pflichtfelder ausdehnen, und defekte Zeilen bekämen stillschweigend einen
    Satz mit Lücken.
    """
    for fehlendes in ("code", "severity", "category", "machine_id", "raised_at"):
        unvollstaendig = {k: v for k, v in ALT_ALARM.items() if k != fehlendes}
        with pytest.raises(KeyError):
            baue_inhalt("alarm_raised", unvollstaendig)

    for fehlendes in ("type", "machine_id", "performed_at"):
        unvollstaendig = {k: v for k, v in ALT_WARTUNG.items() if k != fehlendes}
        with pytest.raises(KeyError):
            baue_inhalt("maintenance_performed", unvollstaendig)


def test_code_darf_none_sein_und_wird_zum_fragezeichen() -> None:
    """Dokumentierte Ausnahme: `code` ist regulär nullbar, anders als die übrigen."""
    satz = baue_inhalt("alarm_raised", {**ALT_ALARM, "code": None})
    assert satz.startswith("Alarm 5 ? (warning/hardware)")


def test_nur_alarm_und_wartung_wurden_um_freitext_erweitert() -> None:
    """Hält die bewusste Begrenzung dieses Changes fest.

    Produktionslauf, Drift, Ereigniskette und Empfehlung bleiben bei der
    Struktur. Bei den ersten beiden gibt es keinen Freitext in der Quelle; bei
    den letzten beiden wäre der Text eine ABLEITUNG des Systems — sie zu
    spiegeln hiesse, das Gedächtnis mit den eigenen Schlüssen zu speisen und
    diese später als Beleg wiederzufinden. Wer das ändern will, soll es
    entscheiden, nicht nebenbei tun.
    """
    unveraendert = {
        "production_run": {
            "product_code": "P-1",
            "line_id": 1,
            "started_at": "2026-06-01T00:00:00+00:00",
        },
        # `machine_id` gehoert dazu: Die Abweichung liest sie seit dem
        # 29.08.2026 HART, weil `drift/service.py` sie immer schreibt und eine
        # Nutzlast ohne sie defekt waere.
        "drift_detected": {"data_point_id": 4, "effect_size": 1.5, "machine_id": 3},
    }
    for event_type, payload in unveraendert.items():
        satz = baue_inhalt(event_type, payload)
        # Ein zusätzliches Freitextfeld darf den Satz NICHT verändern.
        assert baue_inhalt(event_type, {**payload, "description": "sollte ignoriert werden"}) == (
            satz
        )
        assert baue_inhalt(event_type, {**payload, "message": "sollte ignoriert werden"}) == satz


def test_jeder_registrierte_typ_baut_einen_nichtleeren_satz() -> None:
    """Absicherung gegen einen Bauer, der still eine leere Zeichenkette liefert."""
    assert set(CONTENT_BUILDERS) >= {"alarm_raised", "maintenance_performed"}
    for satz in (
        baue_inhalt("alarm_raised", ALT_ALARM),
        baue_inhalt("maintenance_performed", ALT_WARTUNG),
    ):
        assert satz.strip()
        assert not satz.endswith(" ")


# ──────────────────────────────────────────────────────────────────────
#  Der Gegenstand nennt EINE Anlage — die Nummer ist eine Eigenschaft, kein zweiter Name
# ──────────────────────────────────────────────────────────────────────


def test_die_klammer_nennt_die_nummer_als_kennung_nicht_als_zweite_anlage() -> None:
    """DER TRAGENDE FALL (03.09.2026): „PR-01 (Kennung 7)“, nicht „PR-01 (Maschine 7)“.

    Die Gegenstelle bildet ihre Knoten aus dem Satz. „PR-01 (Maschine 7)“ las ihre
    Gewinnung als zwei Anlagen und machte daraus „PR-01 enthaelt Maschine-7“ samt
    Umkehrung — 12 Faktenpaare, Zyklen, reflexive Aussagen. Die Nummer ist der
    Primaerschluessel DERSELBEN Zeile. Ein Eigenschaftswort in der Klammer sagt das;
    ein Anlagenwort behauptet eine Beziehung, die es nicht gibt.
    """
    satz = _gegenstand({"machine_id": 7, "machine_external_id": "PR-01"})
    assert satz == "PR-01 (Kennung 7)", satz
    assert "Maschine" not in satz, "ein zweites Anlagenwort im Satz behauptet eine zweite Anlage"


def test_der_zusatz_teilt_sich_die_klammer_mit_der_kennung() -> None:
    """Die Notiz haengt den Zeitpunkt in DIESELBE Klammer — sonst stuenden zwei hintereinander."""
    satz = _gegenstand(
        {"machine_id": 7, "machine_external_id": "PR-01"}, zusatz="2026-09-02T09:16:57+00:00"
    )
    assert satz == "PR-01 (Kennung 7, 2026-09-02T09:16:57+00:00)", satz


def test_ohne_kennung_bleibt_die_nummer_der_name() -> None:
    """AUFBAU-KONTROLL-ZWILLING: Traegt die Nutzlast keine Anlagenkennung, IST die Nummer

    der einzige Name — dann ist „Maschine 8“ richtig, und ein Knoten dafuer auch. Ohne
    diesen Fall bliebe der Fall oben auch gruen, wenn das Anlagenwort ueberall verschwaende.
    """
    assert _gegenstand({"machine_id": 8}) == "Maschine 8"
    assert _gegenstand({"machine_id": None}, maschine_optional=True) == "ohne Maschinenbezug"
