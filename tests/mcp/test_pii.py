# ============================================================
#  FOREMAN — tests/mcp/test_pii.py
#  Zweck: PII-Schutz der MCP-Outputs festnageln — kein Ausgabeschema exponiert ein
#         Klartext-Identitätsfeld, und zur Laufzeit verlässt nur die pseudonymisierte
#         Form (HMAC-Token) bzw. der NER-maskierte Text den Server. Die Klartext-
#         Identität aus `users` taucht NIE in einem MCP-Output auf (§8, Brief §2).
#  Architektur-Einordnung: MCP-Schicht (F7). Strukturelle (DB-frei) + behaviorale
#         (gegen die Test-DB) Prüfung.
# ============================================================
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.core.pseudonymize import Pseudonymizer
from foreman.db.models import Alarm, Machine, User, WorkerNote
from foreman.mcp import tools
from foreman.mcp.schemas import (
    AlarmOut,
    DriftStatusOut,
    EventChainOut,
    FailurePredictionOut,
    MachineOut,
    NoteHitOut,
    PredictionFactor,
    ReadingPoint,
    ReadingsOut,
    WorkerRecommendationOut,
)

# Klartext-Identitäts-/Geheimnis-Felder, die NIE in einem MCP-Output stehen dürfen.
_FORBIDDEN_FIELD_NAMES = frozenset(
    {"email", "password", "password_hash", "embedding", "user_id", "performed_by", "name"}
)

_ALL_LEAF_OUTPUTS: tuple[type[BaseModel], ...] = (
    MachineOut,
    AlarmOut,
    DriftStatusOut,
    FailurePredictionOut,
    WorkerRecommendationOut,
    EventChainOut,
    NoteHitOut,
    ReadingsOut,
    ReadingPoint,
    PredictionFactor,
)


class _StubProvider:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 1024 for _ in texts]


# ============================================================
#  Strukturell (DB-frei)
# ============================================================
def test_no_output_schema_exposes_cleartext_identity_fields() -> None:
    """Kein Ausgabeschema trägt ein Klartext-Identitäts- oder Geheimnis-Feld."""
    for model in _ALL_LEAF_OUTPUTS:
        fields = set(model.model_fields)
        leaked = fields & _FORBIDDEN_FIELD_NAMES
        assert not leaked, f"{model.__name__} exponiert PII-Feld(er): {sorted(leaked)}"


def test_note_hit_schema_omits_embedding_and_classification() -> None:
    """Der Notiz-Treffer gibt weder Vektor noch KI-Klassifikation aus (PII-/Daten-Minimierung)."""
    fields = set(NoteHitOut.model_fields)
    assert "embedding" not in fields
    assert "classification" not in fields


# ============================================================
#  Behavioral (gegen die Test-DB)
# ============================================================
@pytest.mark.integration
async def test_alarm_output_carries_only_pseudonym_not_cleartext(
    mcp_session: AsyncSession, pseudonymizer: Pseudonymizer
) -> None:
    """Eine quittierte Maschine: der Output trägt den HMAC-Token, nie die Identität aus users."""
    user = User(email="anna.example@werk.de", password_hash="x", role="worker")
    mcp_session.add(user)
    await mcp_session.flush()
    token = pseudonymizer.tokenize_worker(str(user.id))
    machine = Machine(label="CNC-7")
    mcp_session.add(machine)
    await mcp_session.flush()
    mcp_session.add(
        Alarm(
            machine_id=machine.id,
            severity="warning",
            category="process",
            acknowledged_at=datetime.now(UTC),
            acknowledged_by=token,
        )
    )
    await mcp_session.commit()

    result = await tools.get_alarms(machine_id=machine.id)
    dumped = result.model_dump_json()

    acknowledged_by = result.alarms[0].acknowledged_by
    assert token in dumped  # pseudonymer Token ist da
    assert "anna.example@werk.de" not in dumped  # Klartext-Identität nicht
    assert acknowledged_by == token  # genau der HMAC-Token
    assert acknowledged_by != str(user.id)  # Token ≠ rohe user_id


@pytest.mark.integration
async def test_note_search_output_masks_identity(
    mcp_session: AsyncSession,
    pseudonymizer: Pseudonymizer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Notiz-Suche: nur maskierter Text + Autor-Token verlassen den Server."""
    monkeypatch.setattr(tools, "get_embedding_provider", lambda: _StubProvider())
    machine = Machine(label="CNC-9")
    mcp_session.add(machine)
    await mcp_session.flush()
    author = pseudonymizer.tokenize_worker("42")
    mcp_session.add(
        WorkerNote(
            machine_id=machine.id,
            text="[PERSON] meldet Lagergeräusch.",  # bereits NER-maskiert
            author=author,
            embedding=[0.1] * 1024,
        )
    )
    await mcp_session.commit()

    result = await tools.search_notes("Lager", machine_id=machine.id)
    dumped = result.model_dump_json()

    assert result.count == 1
    assert author in dumped
    assert "[PERSON]" in dumped
    # Kein Vektor, keine rohe user_id im Output.
    assert "embedding" not in dumped
    assert '"42"' not in dumped
