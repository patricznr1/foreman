# ============================================================
#  FOREMAN — tests/mcp/security/test_ip_wording.py
#  Zweck: Der Hidden-Term-Scan (Invariante III, Akzeptanzkriterium) — die nach
#         außen sichtbaren Tool-Strings (Name, Beschreibung, Ein-/Ausgabeschema)
#         tragen KEIN internes Vokabular (Library-/Algorithmen-/Substrat-Namen).
#         Das Gedächtnis nach außen nur paraphrasiert.
#  Architektur-Einordnung: MCP-Schicht (F7), Sicherheits-/IP-Akzeptanzkriterium.
# ============================================================
from __future__ import annotations

import json

from foreman.mcp.server import build_mcp_server

# Internes Vokabular, das in keiner extern sichtbaren Tool-Zeichenkette stehen darf.
_FORBIDDEN_TERMS = (
    "pgvector",
    "adwin",
    "hnsw",
    "bge-m3",
    "bge_m3",
    "litellm",
    "lightgbm",
    "river",
    "ollama",
    "qwen",
    "timescale",
    "sqlalchemy",
    "substrate",
    "substrat",
    "nexus",
    "cosine",
    "readings_1m",
    "shap",
    "embedding",
    "vektor",
)


async def test_tool_strings_carry_no_internal_vocabulary() -> None:
    server = build_mcp_server()
    tool_list = await server.list_tools()
    assert tool_list, "Ohne registrierte Tools wäre der Scan trivial bestanden."

    parts: list[str] = []
    for tool in tool_list:
        parts.append(tool.name)
        parts.append(tool.description or "")
        parts.append(json.dumps(tool.inputSchema or {}, ensure_ascii=False))
        output_schema = getattr(tool, "outputSchema", None)
        if output_schema:
            parts.append(json.dumps(output_schema, ensure_ascii=False))
        if tool.annotations is not None and tool.annotations.title:
            parts.append(tool.annotations.title)

    blob = " ".join(parts).lower()
    leaked = [term for term in _FORBIDDEN_TERMS if term in blob]
    assert not leaked, f"Internes Vokabular in extern sichtbaren MCP-Tool-Strings: {leaked}"
