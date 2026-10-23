"""Transport-era behavior: dual-era by default, strict modern-only on demand."""

from __future__ import annotations

from petmcp.protocol import client_meta


def test_legacy_initialize_handshake_is_served_by_default(stdio_server) -> None:
    response = stdio_server.call(
        "initialize",
        {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "legacy", "version": "1.0.0"},
        },
        meta=None,
    )
    result = response["result"]
    assert result["protocolVersion"] == "2025-11-25"
    assert "tools" in result["capabilities"]
    assert result["serverInfo"]["name"] == "pet-hospital-mcp"


def test_legacy_client_can_list_tools(stdio_server) -> None:
    stdio_server.call(
        "initialize",
        {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "legacy", "version": "1.0.0"},
        },
        meta=None,
        request_id=1,
    )
    stdio_server.send_raw({"jsonrpc": "2.0", "method": "notifications/initialized"})
    tools = stdio_server.call("tools/list", {}, meta=None, request_id=2)["result"]
    assert [tool["name"] for tool in tools["tools"]] == ["list_pets", "add_pet"]


def test_modern_connection_rejects_initialize(make_stdio) -> None:
    session = make_stdio()
    discover = session.call("server/discover", {}, meta=client_meta(), request_id=1)
    assert discover["result"]["supportedVersions"] == ["2026-07-28"]

    rejected = session.call(
        "initialize",
        {"protocolVersion": "2025-11-25", "capabilities": {}},
        meta=None,
        request_id=2,
    )
    assert rejected["error"]["code"] == -32022


def test_modern_only_flag_rejects_initialize(make_stdio) -> None:
    session = make_stdio(args=["--modern-only"])
    response = session.call(
        "initialize",
        {"protocolVersion": "2025-11-25", "capabilities": {}},
        meta=None,
        request_id=1,
    )
    assert response["error"]["code"] == -32022
    assert response["error"]["data"]["supported"] == ["2026-07-28"]

    discover = session.call("server/discover", {}, meta=client_meta(), request_id=2)
    assert discover["result"]["supportedVersions"] == ["2026-07-28"]


def test_stdin_close_exits_cleanly(stdio_server) -> None:
    stdio_server.call("server/discover", {}, meta=client_meta())
    stdio_server.close()
    assert stdio_server.proc.returncode == 0
