"""Pet Hospital MCP Server (MVP).

Exposes the Pet Hospital REST API to MCP clients over stdio, implementing the
stateless, per-request-envelope MCP revision ``2026-07-28``.

This first iteration intentionally ships a single tool, ``list_pets``.
"""

__version__ = "0.1.0"

SERVER_NAME = "pet-hospital-mcp"
SERVER_TITLE = "宠物医院 MCP Server"

__all__ = ["__version__", "SERVER_NAME", "SERVER_TITLE"]
