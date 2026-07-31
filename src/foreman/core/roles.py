# ============================================================
#  FOREMAN — core/roles.py
#  Zweck: Kanonische Rollen-Quelle der Plattform (Rollenmatrix 3.1, §5/§20.4).
#  Architektur-Einordnung: Kern-Schicht (Schicht 1) — transport- UND
#         persistenz-neutral. Abo-Autorisierung (`realtime/authz.py`), Route-
#         Guards (`api/deps.require_roles`) und die Nutzer-Anlage
#         (`db/provisioning.py`) ziehen ihr Vokabular von hier, damit es genau
#         EINE Wahrheit gibt. Bewusst in `core/`: `db/` darf nicht aus
#         `realtime/` importieren.
#  Bewusst KEINE `admin`-Rolle (§22.1): die administrative Rolle IST `manager`.
#         Käme später eine echte `admin`-Rolle, wird sie hier additiv ergänzt.
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    """Die vier Rollen der Plattform (Designstudie-Matrix 3.1).

    `StrEnum`, damit die Werte genau die Strings SIND, die in `users.role` stehen:
    bestehende Vergleiche gegen rohe Strings (`user.role in {...}`) bleiben gültig,
    und ein Enum-Wert lässt sich ohne Konvertierung in die Spalte schreiben.
    """

    WORKER = "worker"
    SHIFT_LEAD = "shift_lead"
    TECHNICIAN = "technician"
    MANAGER = "manager"
