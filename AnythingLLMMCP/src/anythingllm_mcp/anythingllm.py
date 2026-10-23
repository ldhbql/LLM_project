"""Thin async REST client for a local AnythingLLM instance.

Only the endpoints needed to answer questions from a single workspace are
implemented. See the AnythingLLM developer API at ``<base_url>/api/docs``.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from .config import Settings
from .models import Answer, Source

AUTH_PATH = "/v1/auth"
WORKSPACES_PATH = "/v1/workspaces"

_REASONING_BLOCK = re.compile(r"<think\b[^>]*>.*?</think\s*>", re.DOTALL | re.IGNORECASE)
_REASONING_OPEN = re.compile(r"<think\b[^>]*>", re.IGNORECASE)


def clean_answer(text: str) -> str:
    """Drop ``<think>...</think>`` reasoning blocks some models leak into their reply."""
    cleaned = _REASONING_BLOCK.sub("", text)
    unclosed = _REASONING_OPEN.search(cleaned)
    if unclosed is not None:
        cleaned = cleaned[: unclosed.start()]
    return cleaned.strip()


def dedupe_sources(sources: list[Source]) -> list[Source]:
    """Remove duplicate sources while preserving order."""
    seen: set[tuple[str, str | None]] = set()
    unique: list[Source] = []
    for source in sources:
        key = (source.title, source.chunk)
        if key not in seen:
            seen.add(key)
            unique.append(source)
    return unique


class AnythingLLMError(RuntimeError):
    """Base class for errors surfaced to the model as a tool error."""


class AnythingLLMAuthError(AnythingLLMError):
    """The API key is missing, invalid, or lacks permission."""


class WorkspaceNotFoundError(AnythingLLMError):
    """The configured (or requested) workspace does not exist."""


class AnythingLLMUnavailableError(AnythingLLMError):
    """The AnythingLLM instance could not be reached or returned a server error."""


class AnythingLLMClient:
    """Minimal client bound to one AnythingLLM instance."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._http = httpx.AsyncClient(
            base_url=settings.api_root,
            headers={
                "Authorization": f"Bearer {settings.api_key}",
                "Accept": "application/json",
            },
            timeout=settings.timeout,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    @property
    def workspace_slug(self) -> str:
        return self._settings.workspace_slug

    async def _request(self, method: str, path: str, *, json: Any | None = None) -> Any:
        try:
            response = await self._http.request(method, path, json=json)
        except httpx.TimeoutException as exc:
            raise AnythingLLMUnavailableError(
                f"请求 AnythingLLM 超时（{self._settings.timeout:g}s）：{path}"
            ) from exc
        except httpx.HTTPError as exc:
            raise AnythingLLMUnavailableError(
                f"无法连接 AnythingLLM（{self._settings.base_url}）：{exc}"
            ) from exc

        if response.status_code in (401, 403):
            raise AnythingLLMAuthError(
                f"AnythingLLM API Key 无效或无权限（HTTP {response.status_code}）。"
            )
        if response.status_code == 404:
            raise WorkspaceNotFoundError(
                f"AnythingLLM 资源不存在（HTTP 404）：{path}。请检查工作区 slug 是否正确。"
            )
        if response.status_code >= 500:
            raise AnythingLLMUnavailableError(
                f"AnythingLLM 服务端错误（HTTP {response.status_code}）：{path}"
            )
        if response.status_code >= 400:
            raise AnythingLLMError(
                f"AnythingLLM 返回错误（HTTP {response.status_code}）："
                f"{response.text[:200]}"
            )

        try:
            return response.json()
        except ValueError as exc:
            raise AnythingLLMError("AnythingLLM 返回了非 JSON 响应。") from exc

    async def verify(self) -> bool:
        """Return ``True`` when the API key is accepted."""
        data = await self._request("GET", AUTH_PATH)
        return bool(data.get("authenticated")) if isinstance(data, dict) else False

    async def list_workspaces(self) -> list[dict[str, Any]]:
        """Return the workspaces available on this instance."""
        data = await self._request("GET", WORKSPACES_PATH)
        workspaces = data.get("workspaces") if isinstance(data, dict) else None
        return workspaces or []

    async def get_workspace(self) -> dict[str, Any]:
        """Return details for the configured workspace."""
        data = await self._request("GET", f"/v1/workspace/{self.workspace_slug}")
        if isinstance(data, dict) and data.get("workspace"):
            return data["workspace"]
        return data if isinstance(data, dict) else {}

    async def ask(self, question: str, *, mode: str = "query") -> Answer:
        """Ask the configured workspace and return a grounded answer."""
        payload = await self._request(
            "POST",
            f"/v1/workspace/{self.workspace_slug}/chat",
            json={"message": question, "mode": mode},
        )
        if not isinstance(payload, dict):
            raise AnythingLLMError("AnythingLLM 返回了非预期的响应结构。")

        error = payload.get("error")
        if error:
            raise AnythingLLMError(f"AnythingLLM 处理失败：{error}")

        text = clean_answer(payload.get("textResponse") or "")
        if not text or payload.get("type") == "abort":
            raise AnythingLLMError("AnythingLLM 未返回回答内容，请稍后重试。")

        sources = dedupe_sources(
            [
                Source(title=str(item.get("title") or "未知来源"), chunk=item.get("chunk"))
                for item in (payload.get("sources") or [])
                if isinstance(item, dict)
            ]
        )
        return Answer(answer=text, sources=sources)
