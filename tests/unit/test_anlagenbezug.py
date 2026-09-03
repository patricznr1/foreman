# ============================================================
#  FOREMAN — tests/unit/test_anlagenbezug.py
#  Zweck: Der Gegenstand einer Spiegelung ist benennbar — im SATZ die konkrete
#         Kennung, in den METADATEN die Klasse.
#  ANLASS (29.08.2026, Befund der Gegenstelle): Das Gedächtnis bildet seine
#         Knoten aus dem Satz. Weil bisher jeder gespiegelte Satz einer Art mit
#         derselben Wortfolge begann, fielen alle Einträge dieser Art auf EINEN
#         Knoten zusammen — 168 Notizen auf einen einzigen. Über den lief die
#         Vererbung, und daraus entstanden rund 1.684 falsche Aussagen.
#         Der zweite Grund wiegt schwerer und gilt unabhängig vom Graphen: DER
#         SATZ IST DIE GRUNDLAGE DER EINBETTUNG. Einträge mit gleichem Anfang
#         teilen einen Vektor-Anteil, der nichts mit ihrem Inhalt zu tun hat.
#  Die Trennung ist tragend: Konkrete Kennungen in den Satz (sie benennen einen
#         Gegenstand), Klassen und Typen in die Metadaten (ein Klassenwort im
#         Satz erzeugt nur eine weitere unbenannte Nabe).
# ============================================================
from __future__ import annotations

from datetime import UTC, datetime

from foreman.db.models import Alarm, WorkerNote
from foreman.ingestion.semantic import Anlagenbezug, alarm_payload, notiz_payload
from foreman.substrate.content import baue_inhalt

BEZUG = Anlagenbezug(
    machine_external_id="AX-02",
    machine_class="servo_axis",
    component_type="bearing",
    component_label="Achslager",
)
LEER = Anlagenbezug()


def _notiz(kennung: int, text: str) -> WorkerNote:
    return WorkerNote(
        id=kennung,
        machine_id=2,
        shift="frueh",
        text=text,
        classification="auffaellig",
        created_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
    )


def _alarm(kennung: int) -> Alarm:
    return Alarm(
        id=kennung,
        machine_id=2,
        component_id=7,
        code="AXIS_VIB_WARN",
        severity="warning",
        category="hardware",
        raised_at=datetime(2026, 6, 14, 10, 0, tzinfo=UTC),
        message=None,
    )


# ──────────────────────────────────────────────────────────────────────
#  Die Metadaten: immer alle vier, auch leer
# ──────────────────────────────────────────────────────────────────────


def test_die_vier_felder_stehen_immer_in_der_nutzlast() -> None:
    """AUFBAU-KONTROLLE: Ein fehlender Schlüssel und ein leerer Wert sind für
    die Gegenstelle VERSCHIEDENE Dinge.

    Sie filtert über diese Felder. Ein Feld, das mal da ist und mal nicht, lässt
    „nicht erhoben" wie „nicht vorhanden" aussehen und zwingt jeden Leser zu
    einer Fallunterscheidung. Deshalb immer alle vier — auch wenn sie leer sind.
    """
    felder = ("machine_external_id", "machine_class", "component_type", "component_label")
    for nutzlast in (
        notiz_payload(_notiz(1, "x"), "x", LEER),
        notiz_payload(_notiz(1, "x"), "x", BEZUG),
        alarm_payload(_alarm(1), None, LEER),
        alarm_payload(_alarm(1), None, BEZUG),
    ):
        for feld in felder:
            assert feld in nutzlast, feld


def test_die_klasse_geht_in_die_metadaten_und_nicht_in_den_satz() -> None:
    """DIE TRAGENDE TRENNUNG.

    `servo_axis` und `bearing` sind Klassenwörter. Im Satz erzeugen sie auf der
    Gegenseite eine weitere unbenannte Nabe, an der alles zusammenläuft — genau
    das Problem, das dieser Change behebt. Als Metadatum sind sie die Achse,
    über die ein Feldvergleich zwei Anlagen verbindet.
    """
    nutzlast = alarm_payload(_alarm(93), None, BEZUG)
    assert nutzlast["machine_class"] == "servo_axis"
    assert nutzlast["component_type"] == "bearing"

    satz = baue_inhalt("alarm_raised", nutzlast)
    assert "servo_axis" not in satz, "Die Maschinenklasse gehört NICHT in den Satz"
    assert "bearing" not in satz, "Der Bauteiltyp gehört NICHT in den Satz"


def test_das_bauteil_des_alarms_geht_mit() -> None:
    """`Alarm.component_id` gibt es seit jeher und fiel beim Spiegeln heraus.

    Es ist die Brücke, auf die es ankommt: Zwei Maschinen ganz verschiedener
    Bauart teilen ein Bauteil, und ein Versagensmuster gehört dem Bauteil.
    """
    assert alarm_payload(_alarm(93), None, BEZUG)["component_id"] == 7


# ──────────────────────────────────────────────────────────────────────
#  Der Satz: der Gegenstand wird benannt
# ──────────────────────────────────────────────────────────────────────


def test_der_satz_nennt_die_anlagenkennung_und_behaelt_die_nummer() -> None:
    """Die Kennung ist der Knoten, die Nummer ist der Rückweg — beides gehört hinein."""
    satz = baue_inhalt(
        "worker_note", notiz_payload(_notiz(4711, "Fügekraft schwankt."), "x", BEZUG)
    )
    assert "AX-02" in satz
    # Die Nummer bleibt — als KENNUNG, nicht als zweite Anlage. „PR-01 (Maschine 7)“ las die
    # Gewinnung der Gegenstelle als zwei Anlagen (03.09.2026); siehe test_substrate_content.
    assert "Kennung 2" in satz
    assert "Maschine" not in satz


def test_zwei_notizen_beginnen_NICHT_mehr_gleich() -> None:
    """DER TRAGENDE FALL — die eigentliche Zusicherung dieses Changes.

    Vorher begann jede Notiz mit „Schichtnotiz zu Maschine N": Bei gleicher
    Maschine waren die ersten vier Wörter zweier Notizen identisch. Genau daraus
    entstand der Sammelknoten, und genau das zieht die Einbettungen zusammen.

    Geprüft wird der SATZANFANG, nicht der ganze Satz: Dass sich zwei Notizen
    irgendwo unterscheiden, war schon immer wahr — sie tragen verschiedenen
    Text. Die Frage ist, ob sie sich DORT unterscheiden, wo die Gegenstelle
    ihren Knotennamen bildet.
    """
    a = baue_inhalt("worker_note", notiz_payload(_notiz(4711, "Fügekraft schwankt."), "a", BEZUG))
    b = baue_inhalt("worker_note", notiz_payload(_notiz(4712, "Lager läuft heiß."), "b", BEZUG))

    assert a.split()[:2] != b.split()[:2], (
        "❌ Zwei Notizen beginnen mit derselben Wortfolge. Auf der Gegenseite fallen sie "
        "damit auf einen Knoten zusammen, und ihre Einbettungen rücken zusammen, ohne "
        "dass der Inhalt etwas damit zu tun hat."
    )
    assert a.startswith("Notiz 4711 ")
    assert b.startswith("Notiz 4712 ")


def test_ohne_bezug_bleibt_der_satz_lesbar() -> None:
    """AUFBAU-KONTROLLE: Der Bezug ist eine Anreicherung, kein Pflichtfeld.

    Eine Anlage ohne gepflegte `external_id` darf die Spiegelung nicht
    verhindern — der Satz fällt dann auf die Maschinennummer zurück. Ohne
    diesen Fall würde eine leere Stammdatenspalte zu einem stillen Ausfall der
    Spiegelung, und zwar nur für die betroffenen Anlagen.
    """
    satz = baue_inhalt("worker_note", notiz_payload(_notiz(4711, "x"), "x", LEER))
    assert satz.startswith("Notiz 4711 zu Maschine 2 (")
    assert "None" not in satz


# ──────────────────────────────────────────────────────────────────────
#  Der Rueckweg: das Bauteil muss ZURUECKKOMMEN, nicht nur hingehen
# ──────────────────────────────────────────────────────────────────────


def test_das_bauteil_ueberlebt_den_rueckweg() -> None:
    """DIE BRUECKE IST ERST GESCHLAGEN, WENN SIE IN BEIDE RICHTUNGEN TRAEGT.

    Gemessen am 01.09.2026 nach dem Neuspiegel-Lauf: Die Stammdaten lagen im
    Gedaechtnis, kamen aber nicht zurueck — `RecallItem` fuehrte die Felder gar
    nicht, und `_memory_hit` liess sie fallen. In 0 von 50 Treffern war ein
    Bauteil zu sehen, obwohl es in jeder Nutzlast stand.

    Das ist die stillste Form des Fehlschlags: Der Schreibweg meldet Erfolg, das
    Gedaechtnis fuehrt die Angabe, und trotzdem kann niemand damit arbeiten.
    """
    from foreman.archive.search import _memory_hit
    from foreman.reasoners.event_chain.recall import map_recall_response

    antwort = {
        "results": [
            {
                "id": "mem-1",
                "content": "Alarm 93 AXIS_VIB_WARN an RB-01 (Maschine 10) ausgelöst.",
                "metadata": {
                    "machine_id": 10,
                    "machine_class": "robot",
                    "component_type": "bearing",
                    "component_label": "Gelenklager Achse 3",
                    "source_type": "alarm",
                    "source_id": 93,
                },
            }
        ]
    }

    treffer = map_recall_response(antwort, max_results=5)
    assert len(treffer) == 1
    item = treffer[0]
    assert item.component_type == "bearing", "Der Bauteiltyp geht beim Auswerten verloren"
    assert item.component_label == "Gelenklager Achse 3"

    hit = _memory_hit(item)
    assert hit.detail["bauteilart"] == "bearing", (
        "❌ Das Bauteil erreicht die Trefferkarte nicht. Damit ist der Fall "
        "'gleiches Bauteil an anderer Maschine' nicht adressierbar, obwohl die "
        "Angabe im Gedaechtnis steht."
    )
    assert hit.detail["bauteil"] == "Gelenklager Achse 3"
    # Und die Maschinenklasse bleibt, wo sie war — keine Verdraengung.
    assert hit.detail["maschinenklasse"] == "robot"


def test_ohne_bauteil_entsteht_kein_leerer_schluessel() -> None:
    """AUFBAU-KONTROLLE: Eine Notiz fuehrt kein Bauteil.

    Ein Schluessel mit leerem Wert in der Trefferkarte behauptete, die Angabe sei
    erhoben und leer — sie ist aber gar nicht vorgesehen. Der Unterschied zaehlt
    fuer den Leser der Karte.
    """
    from foreman.archive.search import _memory_hit
    from foreman.reasoners.event_chain.recall import RecallItem

    hit = _memory_hit(RecallItem(content="Notiz 4711 zu AX-02 (Maschine 2).", machine_id=2))
    assert "bauteilart" not in hit.detail
    assert "bauteil" not in hit.detail
