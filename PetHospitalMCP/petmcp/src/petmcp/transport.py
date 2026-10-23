"""stdio transports.

Two modes:

* **dual-era (default)** - the SDK's own loop: a client that opens with the
  modern per-request envelope (2026-07-28) is served statelessly, while a
  client that opens with the legacy ``initialize`` handshake is served as the
  handshake revision. This is what a *dual-era* server does per the spec, and
  it is required for compatibility with clients whose MCP client predates
  2026-07-28 (e.g. opencode 1.18.x, which has no ``server/discover``).

* **modern-only** (``--modern-only``) - drives the SDK's modern-only stream
  loop, which rejects ``initialize`` with ``UnsupportedProtocolVersionError``
  (-32022). Use it only with clients that speak 2026-07-28.

``_serve_modern_stream`` is a private SDK symbol, pinned by ``mcp==2.2.0`` and
guarded by ``tests/test_transport.py``.
"""

from __future__ import annotations

from typing import Any

from mcp.server.lowlevel import Server
from mcp.server.runner import _serve_modern_stream
from mcp.server.stdio import stdio_server


async def run_stdio(server: Server[Any], *, modern_only: bool = False) -> None:
    """Serve ``server`` over stdin/stdout until the client closes stdin."""
    async with stdio_server() as (read_stream, write_stream):
        if modern_only:
            async with server.lifespan(server) as lifespan_state:
                await _serve_modern_stream(
                    server,
                    read_stream,
                    write_stream,
                    lifespan_state=lifespan_state,
                    raise_exceptions=False,
                )
        else:
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
