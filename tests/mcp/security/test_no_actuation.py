# ============================================================
#  FOREMAN — tests/mcp/security/test_no_actuation.py
#  Zweck: Strukturell beweisen, dass die MCP-Schicht read-only ist — kein Schreib-
#         Muster, kein Reasoner-/LLM-Trigger im Quelltext, und jedes registrierte
#         Tool ist als readOnlyHint/nicht-destruktiv markiert. Die tragende
#         AI-Act-Limited-Risk-Bedingung (keine Aktorik, §10.5) wird hier verriegelt.
#  Architektur-Einordnung: MCP-Schicht (F7), Sicherheits-Akzeptanzkriterium.
# ============================================================
from __future__ import annotations

from pathlib import Path

from foreman import mcp as mcp_pkg
from foreman.mcp.server import build_mcp_server

_MCP_DIR = Path(mcp_pkg.__file__).resolve().parent

# Schreib-/Trigger-Muster, die in read-only Code NIE vorkommen dürfen (Invariante I).
_FORBIDDEN_PATTERNS = (
    "session.add(",
    "session.add_all(",
    "session.delete(",
    "session.merge(",
    "session.commit(",
    ".flush(",
    ".predict(",
    ".recommend(",
    ".reconstruct(",
    "run_machine(",
    "gateway.complete(",
    "INSERT INTO",
    "UPDATE ",
    "DELETE FROM",
)


def test_mcp_source_has_no_write_or_reasoner_trigger() -> None:
    """Kein Schreib-/Trigger-Muster im gesamten MCP-Quelltext."""
    offenders: list[str] = []
    for path in sorted(_MCP_DIR.glob("*.py")):
        # Case-insensitiv: ein Schreib-Muster soll auch in Kleinschreibung auffallen.
        source = path.read_text(encoding="utf-8").lower()
        offenders.extend(
            f"{path.name}: {pattern}"
            for pattern in _FORBIDDEN_PATTERNS
            if pattern.lower() in source
        )
    assert not offenders, f"Schreib-/Trigger-Muster in der MCP-Schicht gefunden: {offenders}"


async def test_every_registered_tool_is_read_only() -> None:
    """Jedes registrierte Tool trägt readOnlyHint=True und ist nicht destruktiv."""
    server = build_mcp_server()
    tool_list = await server.list_tools()
    assert tool_list, "Es muss mindestens ein Tool registriert sein."
    for tool in tool_list:
        assert tool.annotations is not None, f"{tool.name} ohne Annotations"
        assert tool.annotations.readOnlyHint is True, f"{tool.name} nicht read-only markiert"
        assert tool.annotations.destructiveHint is False, f"{tool.name} als destruktiv markiert"
