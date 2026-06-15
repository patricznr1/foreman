# ============================================================
#  FOREMAN — embeddings/errors.py
#  Zweck: Fehlerhierarchie der Embedding-Schicht (F-SEM). Die einzige
#         Fehler-Schnittstelle, die ein Aufrufer (Ingestion, Reasoner, Such-Route)
#         je fängt — keine Backend-/Library-Ausnahme (httpx, sentence-transformers)
#         dringt nach oben durch (harte Architektur-Grenze, analog §13.5 Gateway).
#  Architektur-Einordnung: Querschnitt der Embedding-Schicht (Schicht 2). Vorbild
#         ist die Gateway-Fehlerhierarchie (llm/errors.py): typisierte,
#         deutschsprachige Fehler statt durchgereichter Library-Ausnahmen.
#  Konvention (§6): Fehlermeldungen auf Deutsch; keine PII/keine Notiz-Texte/keine
#         Vektoren in Meldungen.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence


class EmbeddingError(RuntimeError):
    """Basis aller Embedding-Fehler.

    Ein Aufrufer kann mit einem einzigen ``except EmbeddingError`` jede
    Fehlersituation der Embedding-Schicht behandeln, ohne Backend-Interna
    (Ollama/httpx, sentence-transformers) zu kennen.
    """


class ProviderUnavailable(EmbeddingError):
    """Kein erlaubtes Embedding-Backend erreichbar — Fallback verboten oder erschöpft.

    `attempted` listet die in Prioritäts-Reihenfolge erfolglos versuchten
    Backends (für Logging/Observability, keine PII).
    """

    def __init__(self, message: str, *, attempted: Sequence[str] = ()) -> None:
        super().__init__(message)
        self.attempted: tuple[str, ...] = tuple(attempted)


class DimensionMismatch(EmbeddingError):
    """Ein Backend lieferte einen Vektor mit falscher Dimension.

    Die Embedding-Spalte ist `vector(1024)` (GROUND_TRUTH §5) — ein Vektor anderer
    Länge würde beim Insert/Index brechen und macht Treffer unvergleichbar. Wird
    deshalb hart abgewiesen statt verkürzt/aufgefüllt. `expected`/`actual` für die
    Diagnose (reine Längen, keine Vektor-Inhalte).
    """

    def __init__(self, *, expected: int, actual: int) -> None:
        super().__init__(
            f"❌ Embedding-Dimension stimmt nicht: erwartet {expected}, erhalten {actual}."
        )
        self.expected = expected
        self.actual = actual


class EmbeddingTimeout(EmbeddingError):
    """Zeitüberschreitung beim Backend-Aufruf (Timeout-Guard, analog §11.2)."""
