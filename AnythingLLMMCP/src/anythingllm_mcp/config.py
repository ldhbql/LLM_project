"""Configuration loaded from environment variables (optionally a local .env)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse

DEFAULT_BASE_URL = "http://localhost:3001"
DEFAULT_TIMEOUT = 60.0

ENV_BASE_URL = "ANYTHINGLLM_BASE_URL"
ENV_API_KEY = "ANYTHINGLLM_API_KEY"
ENV_WORKSPACE_SLUG = "ANYTHINGLLM_WORKSPACE_SLUG"
ENV_TIMEOUT = "ANYTHINGLLM_TIMEOUT"


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    """Resolved runtime settings for talking to a single AnythingLLM workspace."""

    base_url: str
    api_key: str
    workspace_slug: str
    timeout: float = DEFAULT_TIMEOUT

    @property
    def api_root(self) -> str:
        """Base URL for the AnythingLLM REST API (including the ``/api`` prefix)."""
        return f"{self.base_url.rstrip('/')}/api"


def _clean(value: str | None) -> str:
    return value.strip() if value else ""


def _load_dotenv(path: Path) -> None:
    """Populate ``os.environ`` from a ``.env`` file without overriding real env vars."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def find_dotenv(start: Path) -> Path | None:
    """Find the nearest ``.env`` in ``start`` or any of its parent directories."""
    current = start.resolve()
    for directory in (current, *current.parents):
        candidate = directory / ".env"
        if candidate.is_file():
            return candidate
    return None


def load_settings(
    env: Mapping[str, str] | None = None,
    *,
    dotenv_path: Path | None = None,
) -> Settings:
    """Build :class:`Settings` from the environment.

    Raises :class:`ConfigError` with an actionable message when a required value is
    missing or malformed.
    """
    if env is None:
        resolved_dotenv = dotenv_path if dotenv_path is not None else find_dotenv(Path.cwd())
        if resolved_dotenv is not None:
            _load_dotenv(resolved_dotenv)
        env = os.environ

    base_url = _clean(env.get(ENV_BASE_URL)) or DEFAULT_BASE_URL
    api_key = _clean(env.get(ENV_API_KEY))
    workspace_slug = _clean(env.get(ENV_WORKSPACE_SLUG))

    missing = [
        name
        for name, value in ((ENV_API_KEY, api_key), (ENV_WORKSPACE_SLUG, workspace_slug))
        if not value
    ]
    if missing:
        raise ConfigError(
            "缺少必需的环境变量: "
            + ", ".join(missing)
            + "。请参考 .env.example 进行配置。"
        )

    timeout = DEFAULT_TIMEOUT
    raw_timeout = _clean(env.get(ENV_TIMEOUT))
    if raw_timeout:
        try:
            timeout = float(raw_timeout)
        except ValueError as exc:
            raise ConfigError(f"{ENV_TIMEOUT} 必须是数字，当前为 {raw_timeout!r}。") from exc
        if timeout <= 0:
            raise ConfigError(f"{ENV_TIMEOUT} 必须大于 0，当前为 {timeout}。")

    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigError(
            f"{ENV_BASE_URL} 必须是合法的 http(s) URL，当前为 {base_url!r}。"
        )

    return Settings(
        base_url=base_url,
        api_key=api_key,
        workspace_slug=workspace_slug,
        timeout=timeout,
    )
