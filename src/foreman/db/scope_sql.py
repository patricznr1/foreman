# ============================================================
#  FOREMAN — db/scope_sql.py
#  Zweck: Der Maschinen-Ausschnitt als Bedingung in Roh-SQL (§20.4, Matrix 3.1).
#  Architektur-Einordnung: Datenzugriff (Schicht 3). Die Suchpfade ranken über
#         Postgres-Volltext und Vektor-Distanz und sind deshalb als Roh-SQL
#         geschrieben; ORM-Filter greifen dort nicht. Dieser Baustein bringt den
#         Ausschnitt trotzdem IN die Abfrage, statt danach zu sieben.
#  Warum nicht nachträglich filtern: Beide Suchen begrenzen mit LIMIT auf `k`
#         Kandidaten. Ein Filter DANACH schnitte aus einer bereits gekürzten Liste
#         weiter — ein Werker bekäme leere Antworten, obwohl es Treffer gibt.
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence


def machine_scope_sql(
    *, machine_id: int | None, scope: Sequence[int] | None
) -> tuple[str, dict[str, object]]:
    """Liefert den WHERE-Zusatz samt Parametern für eine Suche über `machine_id`.

    EINE Quelle für beide Suchpfade — die Notiz-Suche und die quellenübergreifende
    Archiv-Suche. Getrennte Bausteine wären die Stelle, an der einer der Pfade den
    Ausschnitt verliert, und ein Treffer aus einer fremden Maschine sieht wie ein
    regulärer aus.

    Zwei unabhängige Einschränkungen, die sich ergänzen statt einander zu ersetzen:

    `machine_id` ist der Wunsch des Aufrufers (Query-Parameter). Ob er ihn stellen
    DARF, entscheidet die Route vorher über den Ausschnitt — hier wird er nur
    angewandt.

    `scope` ist die Grenze der Rolle. `None` heißt unbeschränkt (kein Zusatz).
    Eine LEERE Folge heißt „nichts erlaubt", nicht „kein Filter": `= ANY('{}')`
    ergibt in Postgres FALSE, nicht NULL. Genau das ist das default-deny, das eine
    Rolle ohne jede Zuweisung braucht — die Verwechslung der beiden Fälle wäre der
    gefährlichste Fehler an dieser Stelle, weil ausgerechnet der Nutzer ohne
    Zuweisung die ganze Flotte sähe.

    Der ausdrückliche Cast auf `bigint[]` steht da, weil Postgres den Typ eines
    LEEREN Arrays sonst nicht bestimmen kann — ohne ihn bräche genau der
    default-deny-Fall mit einem Typfehler ab, statt nichts zu liefern.
    """
    teile: list[str] = []
    params: dict[str, object] = {}
    if machine_id is not None:
        teile.append(" AND machine_id = :machine_id")
        params["machine_id"] = machine_id
    if scope is not None:
        teile.append(" AND machine_id = ANY(CAST(:scope_machine_ids AS bigint[]))")
        params["scope_machine_ids"] = list(scope)
    return "".join(teile), params
