"""Runtime configuration for the MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_API_BASE = "http://127.0.0.1:8080"
DEFAULT_TIMEOUT = 10.0
ENV_API_URL = "PET_API_URL"


@dataclass(frozen=True, slots=True)
class ServerConfig:
    """Where to reach the upstream Pet Hospital REST API and how long to wait."""

    api_base: str = DEFAULT_API_BASE
    timeout: float = DEFAULT_TIMEOUT

    @classmethod
    def from_env(
        cls,
        api_base: str | None = None,
        timeout: float | None = None,
    ) -> "ServerConfig":
        """Resolve configuration from explicit values, then ``PET_API_URL``, then defaults."""
        base = api_base or os.environ.get(ENV_API_URL) or DEFAULT_API_BASE
        return cls(api_base=base.rstrip("/"), timeout=timeout if timeout is not None else DEFAULT_TIMEOUT)
