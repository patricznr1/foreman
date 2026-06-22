# ============================================================
#  FOREMAN — tests/audit/test_writer.py
#  Zweck: Unit-Tests des reinen Audit-Writer-Kerns (Sektion I) — Entry-Helfer
#         und Mapping AuditEntry → AuditLog. Kein DB-Zugriff: pinnt den Vertrag
#         (HMAC-Akteur, pseudonyme Werte, Legacy-Spalten-Spiegel) deterministisch.
#  Architektur-Einordnung: Test-Infrastruktur (Quality Gates §10.3).
# ============================================================
from __future__ import annotations

from foreman.audit.schemas import AuditEntry
from foreman.audit.writer import (
    ACTION_HITL_ACKNOWLEDGE,
    ACTION_MCP_RETRIEVAL,
    MCP_ACTOR_ROLE,
    MCP_CONSUMER_LABEL,
    ORIGIN_DASHBOARD,
    ORIGIN_MCP,
    build_audit_log,
    hitl_acknowledge_entry,
    mcp_retrieval_entry,
)
from foreman.core.pseudonymize import Pseudonymizer


def test_build_audit_log_maps_typed_fields_and_mirrors_legacy_columns() -> None:
    entry = AuditEntry(
        action_type=ACTION_MCP_RETRIEVAL,
        origin=ORIGIN_MCP,
        actor="v1:deadbeef",
        actor_role=MCP_ACTOR_ROLE,
        target_kind="machine",
        target_id=42,
        machine_id=42,
        detail={"tool": "get_machine", "result": "ok"},
    )

    row = build_audit_log(entry)

    assert row.action_type == ACTION_MCP_RETRIEVAL
    assert row.origin == ORIGIN_MCP
    assert row.actor == "v1:deadbeef"
    assert row.actor_role == MCP_ACTOR_ROLE
    assert row.target_kind == "machine"
    assert row.target_id == 42
    assert row.machine_id == 42
    assert row.detail == {"tool": "get_machine", "result": "ok"}
    # Legacy-NOT-NULL-Spalte `action` wird mit dem action_type gespiegelt.
    assert row.action == ACTION_MCP_RETRIEVAL
    # Legacy-`target` als menschenlesbarer Spiegel des typisierten Ziels.
    assert row.target == "machine:42"
    # §8: kein Klartext-Personenbezug — der user_id-FK bleibt LEER.
    assert row.user_id is None


def test_build_audit_log_legacy_target_without_id_uses_kind_only() -> None:
    entry = AuditEntry(action_type=ACTION_MCP_RETRIEVAL, origin=ORIGIN_MCP, target_kind="machine")
    row = build_audit_log(entry)
    assert row.target == "machine"


def test_build_audit_log_without_target_leaves_legacy_target_none() -> None:
    entry = AuditEntry(action_type=ACTION_MCP_RETRIEVAL, origin=ORIGIN_MCP)
    row = build_audit_log(entry)
    assert row.target is None


def test_mcp_retrieval_entry_uses_pseudonymous_single_consumer_actor(
    pseudonymizer: Pseudonymizer,
) -> None:
    entry = mcp_retrieval_entry(
        pseudo=pseudonymizer,
        tool="get_machine",
        target_kind="machine",
        target_id=7,
        machine_id=7,
        success=True,
    )

    # Akteur = pseudonymisiertes Single-Consumer-Label (kein Klartext, §8 / Test 6).
    assert entry.actor == pseudonymizer.tokenize_worker(MCP_CONSUMER_LABEL)
    assert entry.actor is not None
    assert ":" in entry.actor and MCP_CONSUMER_LABEL not in entry.actor
    assert entry.actor_role == MCP_ACTOR_ROLE
    assert entry.action_type == ACTION_MCP_RETRIEVAL
    assert entry.origin == ORIGIN_MCP
    assert entry.target_kind == "machine"
    assert entry.target_id == 7
    assert entry.machine_id == 7
    assert entry.detail == {"tool": "get_machine", "result": "ok"}


def test_mcp_retrieval_entry_marks_failed_calls_in_detail(pseudonymizer: Pseudonymizer) -> None:
    entry = mcp_retrieval_entry(
        pseudo=pseudonymizer,
        tool="get_machine",
        target_kind="machine",
        target_id=7,
        machine_id=7,
        success=False,
    )
    assert entry.detail == {"tool": "get_machine", "result": "error"}


def test_hitl_acknowledge_entry_pseudonymizes_actor_over_user_id(
    pseudonymizer: Pseudonymizer,
) -> None:
    entry = hitl_acknowledge_entry(
        pseudo=pseudonymizer,
        user_id="55",
        actor_role="manager",
        alarm_id=9,
        machine_id=3,
        alarm_code="DRIFT",
        severity="warning",
    )

    # Akteur ist exakt der HMAC-Token über die user_id — wie acknowledged_by (§8).
    assert entry.actor == pseudonymizer.tokenize_worker("55")
    assert entry.actor_role == "manager"
    assert entry.action_type == ACTION_HITL_ACKNOWLEDGE
    assert entry.origin == ORIGIN_DASHBOARD
    assert entry.target_kind == "alarm"
    assert entry.target_id == 9
    assert entry.machine_id == 3
    assert entry.detail == {
        "decision": "acknowledge",
        "alarm_code": "DRIFT",
        "severity": "warning",
    }
