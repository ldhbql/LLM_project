"""MCP 2026-07-28 protocol constants and small helpers.

The heavy lifting (per-request envelope validation, version negotiation,
``resultType`` and ``serverInfo`` stamping, stdio framing) is done by the
official ``mcp`` SDK. This module pins the values this server relies on so the
wiring, tests and docs share one source of truth.
"""

from __future__ import annotations

from typing import Any, Final

# The only protocol revision this server speaks. It is a *modern* revision:
# every request carries its version and client capabilities in ``params._meta``;
# there is no ``initialize`` handshake and no session.
PROTOCOL_VERSION: Final[str] = "2026-07-28"

# Reserved ``_meta`` keys (see spec: basic/index#_meta).
META_PROTOCOL_VERSION: Final[str] = "io.modelcontextprotocol/protocolVersion"
META_CLIENT_INFO: Final[str] = "io.modelcontextprotocol/clientInfo"
META_CLIENT_CAPABILITIES: Final[str] = "io.modelcontextprotocol/clientCapabilities"
META_SERVER_INFO: Final[str] = "io.modelcontextprotocol/serverInfo"

# Required on every request for a modern revision.
REQUIRED_CLIENT_META_KEYS: Final[frozenset[str]] = frozenset({META_PROTOCOL_VERSION, META_CLIENT_CAPABILITIES})

# JSON-RPC / MCP error codes used by this server.
INVALID_PARAMS: Final[int] = -32602  # malformed params; also "unknown tool" and "resource not found"
METHOD_NOT_FOUND: Final[int] = -32601
INTERNAL_ERROR: Final[int] = -32603
UNSUPPORTED_PROTOCOL_VERSION: Final[int] = -32022

# Cache hints for the two cacheable methods this server serves.
TOOLS_LIST_TTL_MS: Final[int] = 3_600_000
DISCOVER_TTL_MS: Final[int] = 3_600_000
CACHE_SCOPE_PUBLIC: Final[str] = "public"


def client_meta(
    *,
    protocol_version: str = PROTOCOL_VERSION,
    client_name: str = "client",
    client_version: str = "1.0.0",
    capabilities: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the ``_meta`` envelope a modern client must attach to every request.

    Handy for tests, examples and the integration harness. Servers do not send
    this, they validate it.
    """
    meta: dict[str, Any] = {
        META_PROTOCOL_VERSION: protocol_version,
        META_CLIENT_INFO: {"name": client_name, "version": client_version},
        META_CLIENT_CAPABILITIES: capabilities if capabilities is not None else {},
    }
    return meta


def has_modern_envelope(params: Any) -> bool:
    """Return True when ``params`` carries the required modern ``_meta`` fields."""
    if not isinstance(params, dict):
        return False
    meta = params.get("_meta")
    if not isinstance(meta, dict):
        return False
    return REQUIRED_CLIENT_META_KEYS.issubset(meta.keys())
