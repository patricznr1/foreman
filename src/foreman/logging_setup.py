# ============================================================
#  FOREMAN — logging_setup.py
#  Zweck: Strukturiertes Logging mit Emoji-Prefix, keine PII.
#  Architektur-Einordnung: Querschnitt (Schicht 2). Grundlage der
#         Observability (§11.1: Latenz/Erfolg/Fehler je Aufruf).
#  Konvention (§6): Emoji-Prefix, Fehlermeldungen auf Deutsch, niemals PII
#         (keine Klarnamen, keine Tokens, keine Roh-Schichtberichte) loggen.
# ============================================================
from __future__ import annotations

import logging
import sys
from typing import Final

# Einheitliche Emoji-Prefixe (Konvention §6) — von aufrufenden Modulen genutzt.
OK: Final = "✅"
ERROR: Final = "❌"
RETRY: Final = "🔄"
INFO: Final = "📋"
REASON: Final = "🧠"
ALERT: Final = "🔥"
MEMORY: Final = "📚"
SLEEP: Final = "💤"

_CONFIGURED = False


def setup_logging(level: str = "INFO") -> None:
    """Konfiguriert das Wurzel-Logging einmalig (idempotent).

    Bewusst schlankes, gut lesbares Konsolen-Format mit Zeitstempel, Level und
    Logger-Namen. Strukturierte Felder (Latenz/Backend/Erfolg) hängen die
    aufrufenden Module als `key=value` an die Nachricht.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    # Emoji-Prefixe (§6) brauchen UTF-8 — sonst crasht der Handler auf Windows-
    # Konsolen (cp1252). Auf Linux/Docker ist UTF-8 ohnehin Default.
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):  # pragma: no cover — z. B. umgeleiteter Stream
            pass

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # Uvicorn-Access-Logs zähmen — Request-Details kommen strukturiert über uns.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Liefert einen benannten Logger (Konvention: Modul-/Komponenten-Name)."""
    return logging.getLogger(name)
