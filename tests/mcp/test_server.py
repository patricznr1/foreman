# ============================================================
#  FOREMAN — tests/mcp/test_server.py
#  Zweck: Den MCP-Server festnageln — die Tool-Registry (alle read-only Tools), den
#         echten SDK-Handshake (Initialize + list_tools über eine In-Memory-Client-
#         Session), die offene /metrics-Route mit den foreman_mcp_*-Kennzahlen und
#         das Auth-Wiring (offene Pfade frei, MCP-Transport hinter dem Token).
#  Architektur-Einordnung: MCP-Schicht (F7). Integrationsnah, aber DB-frei.
# ============================================================
from __future__ import annotations

from mcp.shared.memory import create_connected_server_and_client_session as client_session
from pydantic import SecretStr

from foreman.mcp.auth import McpSettings
from foreman.mcp.server import build_mcp_app, build_mcp_server
from foreman.observability.metrics import observe_mcp_call, render_metrics

_EXPECTED_TOOLS = {
    "list_machines",
    "get_machine",
    "get_drift_status",
    "get_alarms",
    "list_failure_predictions",
    "get_failure_prediction",
    "get_worker_recommendation",
    "list_event_chains",
    "get_event_chain",
    "search_notes",
    "get_readings",
}


async def test_registry_exposes_all_read_only_tools() -> None:
    server = build_mcp_server(mcp_settings=McpSettings(_env_file=None))
    tool_list = await server.list_tools()

    assert {tool.name for tool in tool_list} == _EXPECTED_TOOLS
    for tool in tool_list:
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False


async def test_sdk_handshake_lists_tools() -> None:
    """Echter MCP-Handshake über eine In-Memory-Client-Session (SDK)."""
    server = build_mcp_server(mcp_settings=McpSettings(_env_file=None))
    async with client_session(server) as client:
        result = await client.list_tools()
    assert {tool.name for tool in result.tools} == _EXPECTED_TOOLS


def test_metrics_render_includes_mcp_counters() -> None:
    observe_mcp_call(tool="list_machines", latency_seconds=0.01, success=True)
    body, _content_type = render_metrics()
    rendered = body.decode("utf-8")
    assert "foreman_mcp_requests_total" in rendered
    assert "foreman_mcp_latency_seconds" in rendered


async def _drive(app: object, *, path: str, method: str) -> tuple[int | None, bytes]:
    scope = {
        "type": "http",
        "path": path,
        "raw_path": path.encode(),
        "method": method,
        "headers": [],
        "query_string": b"",
    }
    statuses: list[int] = []
    body = bytearray()

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, object]) -> None:
        if message["type"] == "http.response.start":
            statuses.append(int(message["status"]))  # type: ignore[call-overload]
        elif message["type"] == "http.response.body":
            body.extend(bytes(message.get("body", b"")))  # type: ignore[arg-type]

    await app(scope, receive, send)  # type: ignore[operator]
    return (statuses[0] if statuses else None, bytes(body))


async def test_app_open_paths_free_and_mcp_behind_token() -> None:
    settings = McpSettings(_env_file=None, token=SecretStr("server-token-0123456789abcdef"))
    app = build_mcp_app(mcp_settings=settings)

    health_status, _ = await _drive(app, path="/health", method="GET")
    assert health_status == 200

    metrics_status, metrics_body = await _drive(app, path="/metrics", method="GET")
    assert metrics_status == 200
    assert b"foreman_mcp_requests_total" in metrics_body

    # Der MCP-Transport ist ohne Token verriegelt.
    mcp_status, _ = await _drive(app, path="/mcp", method="POST")
    assert mcp_status == 401
