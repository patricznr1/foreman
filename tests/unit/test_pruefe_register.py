# ============================================================
#  FOREMAN — tests/unit/test_pruefe_register.py
#  Zweck: Belegt, dass `tools/pruefe_register.py` wirklich anschlaegt. Jede
#         Zusicherung wird EINZELN verletzt; genau die zugehoerige Beanstandung
#         muss kommen und keine fremde.
#  WARUM SO: Eine Pruefung, die nur gegen den gesunden Bestand gruen laeuft,
#         belegt nichts — sie koennte auch leer sein. Der Aufbau-Kontrollzwilling
#         (`test_das_basisregister_ist_sauber`) haelt dagegen: Waere schon die
#         Ausgangslage beanstandet, pruefte kein Negativtest mehr das, was er
#         zu pruefen vorgibt.
#  Architektur-Einordnung: Werkzeug-Test, kein Anwendungscode.
# ============================================================
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml
from tools.pruefe_register import (
    ANSICHT,
    REGISTER,
    pruefe_ansicht,
    pruefe_eintraege,
    pruefe_kopf,
)

BASIS: dict[str, Any] = {
    "schema_version": 1,
    "projekt": "foreman",
    "produkt": "FOREMAN",
    "stand": "2026-09-07",
    "claims": [
        {
            "id": "C-001",
            "aussage": "Die Anlage meldet drei von vier Bausteinen als gebaut.",
            "status": "gemessen",
            "wert": "3 von 4",
            "bedingung": "Gegen den Bestand vom 07.09.2026 erhoben.",
            "datum": "2026-09-01",
            "fundstelle": ["src/foreman/main.py"],
            "geltung": "gueltig",
            "freigabe": ["intern", "fach"],
        },
        {
            "id": "C-002",
            "aussage": "Die zweite Aussage steht hier.",
            "status": "geschaetzt",
            "wert": "zwei",
            "bedingung": "Aus dem Bauzustand abgeleitet.",
            "datum": "2026-08-30",
            "fundstelle": ["GROUND_TRUTH.md"],
            "geltung": "ueberholt",
            "geltung_grund": "Überholt am 07.09.2026 durch die zweite Messung.",
            "freigabe": ["intern"],
        },
    ],
}

ANSICHT_TEXT = """# Aussagen-Register — foreman

Stand: 2026-09-07

| ID | Aussage | Status |
|---|---|---|
| C-001 | Die Anlage meldet drei von vier Bausteinen als gebaut. | gemessen |
| C-002 | Die zweite Aussage steht hier. | geschaetzt |
"""


def _register(**aenderung: Any) -> dict[str, Any]:
    """Eine Kopie des Basisregisters mit genau einer geänderten Kopfangabe."""
    r = copy.deepcopy(BASIS)
    r.update(aenderung)
    return r


def _mit_eintrag(**feld: Any) -> dict[str, Any]:
    """Eine Kopie, in der der ERSTE Eintrag die übergebenen Felder trägt."""
    r = copy.deepcopy(BASIS)
    r["claims"][0].update(feld)
    return r


def _texte(verstoesse: list[Any]) -> str:
    return " | ".join(v.was for v in verstoesse)


# --------------------------------------------------------------------------
#  AUFBAU-KONTROLLE — ohne sie prüft keiner der Negativtests etwas.
# --------------------------------------------------------------------------


def test_das_basisregister_ist_sauber() -> None:
    """Der Zwilling zu allen Negativtests: die Ausgangslage wird NICHT beanstandet."""
    r = copy.deepcopy(BASIS)
    assert pruefe_kopf(r) == []
    assert pruefe_eintraege(r) == []
    assert pruefe_ansicht(r, ANSICHT_TEXT) == []


# --------------------------------------------------------------------------
#  KOPF
# --------------------------------------------------------------------------


@pytest.mark.parametrize("feld", ["schema_version", "projekt", "produkt", "stand", "claims"])
def test_ein_fehlendes_kopffeld_wird_benannt(feld: str) -> None:
    verstoesse = pruefe_kopf(_register(**{feld: None}))
    assert any(feld in v.was for v in verstoesse), _texte(verstoesse)


# --------------------------------------------------------------------------
#  EINTRAEGE — je Zusicherung eine Verletzung
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "feld", ["aussage", "status", "bedingung", "datum", "fundstelle", "geltung", "freigabe"]
)
def test_ein_fehlendes_pflichtfeld_wird_benannt(feld: str) -> None:
    verstoesse = pruefe_eintraege(_mit_eintrag(**{feld: None}))
    assert any("Pflichtfeld" in v.was and feld in v.was for v in verstoesse), _texte(verstoesse)


def test_eine_doppelte_kennung_faellt_auf() -> None:
    """Zwei Aussagen unter einem Namen — jede Fundstelle zeigte dann auf beide."""
    r = copy.deepcopy(BASIS)
    r["claims"][1]["id"] = "C-001"
    verstoesse = pruefe_eintraege(r)
    assert any("doppelt" in v.was for v in verstoesse), _texte(verstoesse)


def test_eine_kennung_ohne_muster_faellt_auf() -> None:
    verstoesse = pruefe_eintraege(_mit_eintrag(id="C-1"))
    assert any("Muster" in v.was for v in verstoesse), _texte(verstoesse)


def test_ein_unbekannter_status_faellt_auf() -> None:
    verstoesse = pruefe_eintraege(_mit_eintrag(status="behauptet"))
    assert any("Status" in v.was and "behauptet" in v.was for v in verstoesse), _texte(verstoesse)


def test_eine_unbekannte_geltung_faellt_auf() -> None:
    verstoesse = pruefe_eintraege(_mit_eintrag(geltung="vielleicht"))
    assert any("Geltung" in v.was for v in verstoesse), _texte(verstoesse)


def test_eine_unbekannte_freigabe_faellt_auf() -> None:
    verstoesse = pruefe_eintraege(_mit_eintrag(freigabe=["intern", "presse"]))
    assert any("Freigabe" in v.was and "presse" in v.was for v in verstoesse), _texte(verstoesse)


def test_eine_zu_lange_aussage_faellt_auf() -> None:
    """Eine Aussage ist ein Satz. Wird sie ein Absatz, prüft niemand mehr, was gilt."""
    verstoesse = pruefe_eintraege(_mit_eintrag(aussage="A" * 201))
    assert any("länger" in v.was for v in verstoesse), _texte(verstoesse)


def test_die_grenze_von_200_zeichen_ist_noch_erlaubt() -> None:
    """Grenzwert, nicht nur der Überschreiter: 200 Zeichen sind zulässig."""
    assert pruefe_eintraege(_mit_eintrag(aussage="A" * 200)) == []


def test_ein_datum_nach_dem_stand_faellt_auf() -> None:
    verstoesse = pruefe_eintraege(_mit_eintrag(datum="2026-09-08"))
    assert any("Stand" in v.was for v in verstoesse), _texte(verstoesse)


def test_ueberholt_ohne_grund_faellt_auf() -> None:
    r = copy.deepcopy(BASIS)
    del r["claims"][1]["geltung_grund"]
    verstoesse = pruefe_eintraege(r)
    assert any("geltung_grund" in v.was for v in verstoesse), _texte(verstoesse)


def test_ueberholt_mit_freigabe_nach_aussen_faellt_auf() -> None:
    """Was nicht mehr gilt, darf das Haus nicht verlassen — der Empfänger sieht es ihm nicht an."""
    r = copy.deepcopy(BASIS)
    r["claims"][1]["freigabe"] = ["intern", "kunde"]
    verstoesse = pruefe_eintraege(r)
    assert any("kunde" in v.was for v in verstoesse), _texte(verstoesse)


# --------------------------------------------------------------------------
#  ANSICHT — der Fall, gegen den das Werkzeug gebaut ist
# --------------------------------------------------------------------------


def test_eine_geaenderte_aussage_ohne_neuerzeugung_faellt_auf() -> None:
    """DER TRAGENDE FALL: Eintrag geändert, Ansicht nicht neu erzeugt.

    Die Ansicht liegt im öffentlichen Repository. Driftet sie, steht draußen
    etwas anderes als im Register — und nichts merkt es.
    """
    r = _mit_eintrag(aussage="Die Anlage meldet inzwischen vier von vier Bausteinen.")
    verstoesse = pruefe_ansicht(r, ANSICHT_TEXT)
    assert any("C-001" in v.was for v in verstoesse), _texte(verstoesse)


def test_ein_neuer_eintrag_ohne_neuerzeugung_faellt_auf() -> None:
    r = copy.deepcopy(BASIS)
    r["claims"].append({**BASIS["claims"][0], "id": "C-003"})
    verstoesse = pruefe_ansicht(r, ANSICHT_TEXT)
    assert any("C-003" in v.was and "nicht in der Ansicht" in v.was for v in verstoesse), _texte(
        verstoesse
    )


def test_ein_eintrag_nur_in_der_ansicht_faellt_auf() -> None:
    """Die andere Richtung: gelöscht im Register, stehen geblieben in der Ansicht."""
    verstoesse = pruefe_ansicht(BASIS, ANSICHT_TEXT + "| C-009 | Etwas Fremdes. | gemessen |\n")
    assert any("C-009" in v.was and "nicht im Register" in v.was for v in verstoesse), _texte(
        verstoesse
    )


def test_ein_veralteter_stand_in_der_ansicht_faellt_auf() -> None:
    verstoesse = pruefe_ansicht(_register(stand="2026-09-09"), ANSICHT_TEXT)
    assert any("Stand" in v.was for v in verstoesse), _texte(verstoesse)


def test_der_ansichtsvergleich_bleibt_einzeilig() -> None:
    """Die Ansicht trägt unter Windows CRLF; das darf keinen Befund auslösen.

    EHRLICHER VERMERK: Dieser Test hielt am 07.09.2026 in der Mutationsprobe
    stand, als die Zeilenenden-Umwandlung aus dem Prüfer entfernt wurde — sie
    war wirkungslos, weil hier jeder Vergleich einzeilig ist. Der Test bleibt
    trotzdem: Er wird rot, sobald jemand einen MEHRZEILIGEN Vergleich einbaut,
    ohne die Zeilenenden zu behandeln. Er sichert die Bauart, nicht eine Zeile.
    """
    assert pruefe_ansicht(BASIS, ANSICHT_TEXT.replace("\n", "\r\n")) == []


# --------------------------------------------------------------------------
#  VERBINDUNG ZUR WIRKLICHKEIT
# --------------------------------------------------------------------------


def test_das_echte_register_haelt_seine_eigenen_regeln_ein() -> None:
    """Ohne diesen Test prüfte alles oben nur erfundene Register."""
    roh = yaml.safe_load(Path(REGISTER).read_text(encoding="utf-8"))
    ansicht = Path(ANSICHT).read_text(encoding="utf-8")
    verstoesse = pruefe_kopf(roh) + pruefe_eintraege(roh) + pruefe_ansicht(roh, ansicht)
    assert verstoesse == [], _texte(verstoesse)


# --------------------------------------------------------------------------
#  ZEILENBINDUNG UND FORM — zwei Befunde an #174, am Code bestätigt (07.09.2026)
# --------------------------------------------------------------------------


def test_eine_aussage_in_einer_fremden_zeile_faellt_auf() -> None:
    """Die Aussage von C-001 steht in der Ansicht — aber in der Zeile von C-002.

    Bis dahin suchte der Prüfer die Aussage in der GANZEN Ansicht: Eine
    veraltete Zeile blieb unbemerkt, solange der Text irgendwo stand, und das
    Gate meldete Drift als synchron. Die Aussage gehört in die Zeile IHRER
    Kennung.
    """
    vertauscht = ANSICHT_TEXT.replace(
        "| C-001 | Die Anlage meldet drei von vier Bausteinen als gebaut. | gemessen |",
        "| C-001 | Veraltete Fassung der ersten Aussage. | gemessen |",
    ).replace(
        "| C-002 | Die zweite Aussage steht hier. | geschaetzt |",
        "| C-002 | Die zweite Aussage steht hier. "
        "Die Anlage meldet drei von vier Bausteinen als gebaut. | geschaetzt |",
    )
    # AUFBAU-KONTROLLE: Der Text steht noch in der Ansicht — nur in der falschen Zeile.
    assert "Die Anlage meldet drei von vier Bausteinen als gebaut." in vertauscht
    verstoesse = pruefe_ansicht(BASIS, vertauscht)
    assert any("C-001" in v.was and "ihrer Zeile" in v.was for v in verstoesse), _texte(verstoesse)


def test_ein_stand_nur_in_der_prosa_faellt_auf() -> None:
    """`Stand: <datum>` ist eine Kopfzeile, kein Teilstring irgendwo im Text."""
    ohne_kopfzeile = ANSICHT_TEXT.replace(
        "\nStand: 2026-09-07\n", "\nHinweis: Stand: 2026-09-07 galt gestern.\n"
    )
    assert "Stand: 2026-09-07" in ohne_kopfzeile  # AUFBAU-KONTROLLE: der Teilstring ist da
    verstoesse = pruefe_ansicht(BASIS, ohne_kopfzeile)
    assert any("Stand" in v.was for v in verstoesse), _texte(verstoesse)


def test_claims_als_mapping_gibt_einen_verstoss_und_keinen_traceback() -> None:
    """Der Kopf meldet die Form; die anderen Prüfungen dürfen danach nicht werfen."""
    r = _register(claims={"C-001": {"aussage": "x"}})
    assert any("keine Liste" in v.was for v in pruefe_kopf(r)), _texte(pruefe_kopf(r))
    # Die Form meldet der Kopf GENAU EINMAL. Die anderen Prüfungen geben leer
    # zurück — sonst iterierten sie über die Schlüssel des Mappings und
    # meldeten jeden als „kein Mapping“: vier Rausch-Verstöße für einen Fehler.
    assert pruefe_eintraege(r) == [], _texte(pruefe_eintraege(r))
    assert pruefe_ansicht(r, ANSICHT_TEXT) == [], _texte(pruefe_ansicht(r, ANSICHT_TEXT))


def test_ein_skalarer_eintrag_wird_als_verstoss_benannt() -> None:
    r = copy.deepcopy(BASIS)
    r["claims"].append("nur ein Text statt eines Eintrags")
    verstoesse = pruefe_eintraege(r) + pruefe_ansicht(r, ANSICHT_TEXT)
    assert any("kein Mapping" in v.was for v in verstoesse), _texte(verstoesse)
