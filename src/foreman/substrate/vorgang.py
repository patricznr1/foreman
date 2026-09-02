# ============================================================
#  FOREMAN — src/foreman/substrate/vorgang.py
#  Zweck: Baut die Vorgangskennung, die jeder Gedaechtnis-Abruf mitschickt.
#  Warum es die gibt: Die Gegenstelle legt je Abruf ein Protokoll an — Dauer,
#         Kandidatenzahl je Ebene, ob der Nachsortierer lief, Herkunft je
#         ausgeliefertem Treffer. Alles Angaben, die aus der ANTWORT nicht zu
#         sehen sind. Die Kennung ist der einzige Weg, einen Vorgang von hier mit
#         dem zu verbinden, was DORT geschah.
#  Warum nicht ueber den Zeitstempel: Das ist die Kruecke, die bei mehreren
#         gleichzeitigen Anfragen still das falsche Paar bildet und dabei
#         plausibel aussieht. Ein Messwert aus einer Verwechslung ist nicht
#         unbrauchbar — er ist irrefuehrend.
#  DIE TRAGENDE GESTALTUNGSENTSCHEIDUNG — kein Freitext, strukturell:
#         Die Kennung verlaesst das Haus und landet im Protokoll eines fremden
#         Dienstes. Sie darf deshalb NIE personenbezogene Daten tragen. Das wird
#         hier nicht per Disziplin sichergestellt, sondern ueber die Typen: Der
#         Vorgang ist ein fester Wert, der Bezug eine ZAHL. Es gibt keinen
#         Parameter, durch den ein Werker-Freitext oder eine Suchanfrage
#         hineingereicht werden koennte — auch nicht versehentlich.
# ============================================================
from __future__ import annotations

from typing import Literal
from uuid import uuid4

# Die Vorgaenge, die das Gedaechtnis befragen. Bewusst eine geschlossene Menge:
# Ein freier Name waere die Tuer, durch die doch wieder Text ginge.
Vorgang = Literal["kette", "archiv"]

# Vertrag der Gegenstelle. Der Klient kuerzt zwar ohnehin, aber eine Kennung, die
# erst dort gekuerzt wird, ist am Ende nicht mehr die, die wir gebaut haben.
MAX_LAENGE = 128

# Laenge des Unterscheiders. Zwoelf Hex-Zeichen sind 48 Bit — bei den Abrufzahlen
# dieser Anlage ist eine Kollision ausgeschlossen, und die Kennung bleibt lesbar.
_UNTERSCHEIDER_LAENGE = 12

# Steht fuer "kein Bezug angegeben". Ein leeres Feld waere von der Zahl 0 nicht zu
# unterscheiden, und 0 ist eine gueltige Kennung.
_OHNE_BEZUG = "alle"


def vorgangskennung(vorgang: Vorgang, *, bezug: int | None = None) -> str:
    """Eine Kennung fuer GENAU EINEN Abruf.

    `vorgang` sagt, WAS gefragt hat (Ereigniskette oder Archiv-Suche), `bezug`
    WORAUF es sich bezog — die Kennung des Anker-Alarms bzw. der Maschine, oder
    None fuer "ueber alle".

    JE AUFRUF VERSCHIEDEN, und das ist keine Zierde: Zwei Abrufe zum selben Anker
    faenden im fremden Protokoll sonst dieselbe Zeile, und genau die Frage, welcher
    der beiden langsam war, waere nicht mehr zu beantworten. Der Unterscheider ist
    deshalb zufaellig und nicht etwa der Zeitstempel — siehe Kopf.
    """
    teil = _OHNE_BEZUG if bezug is None else str(bezug)
    return f"{vorgang}-{teil}-{uuid4().hex[:_UNTERSCHEIDER_LAENGE]}"[:MAX_LAENGE]
