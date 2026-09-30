"""HTTP client for the upstream Pet Hospital REST API.

All upstream responses use the envelope::

    {"code": 200, "message": "ok", "data": {...}, "time": "..."}

This client unwraps ``data`` and converts any failure (transport error, non-2xx
status, unexpected ``code``, malformed body) into :class:`UpstreamError`, which
the tool layer turns into an MCP tool-execution error (``isError: true``).
Validation failures (HTTP 400) carry a human-readable ``message`` that is
surfaced verbatim so the model can self-correct.
"""

from __future__ import annotations

from typing import Any

import httpx2

from .config import ServerConfig


class UpstreamError(Exception):
    """The Pet Hospital API was unreachable or answered with an error."""


def _envelope_message(response: httpx2.Response) -> str | None:
    """Best-effort extraction of the upstream ``message`` field for error text."""
    try:
        body = response.json()
    except ValueError:
        return None
    if isinstance(body, dict) and isinstance(body.get("message"), str):
        return body["message"]
    return None


class PetHospitalClient:
    """Thin async wrapper over the Pet Hospital REST API."""

    def __init__(self, config: ServerConfig) -> None:
        self._config = config
        self._client = httpx2.AsyncClient(
            base_url=config.api_base,
            timeout=config.timeout,
            headers={"Accept": "application/json"},
        )

    @property
    def api_base(self) -> str:
        return self._config.api_base

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        ok_status: tuple[int, ...] = (200,),
        ok_codes: tuple[int, ...] = (200,),
    ) -> dict[str, Any]:
        try:
            response = await self._client.request(method, path, params=params, json=json_body)
        except httpx2.RequestError as exc:
            raise UpstreamError(
                f"无法连接宠物医院服务 {self.api_base}：请先启动 pethospital.exe。"
                f"（{type(exc).__name__}: {exc}）"
            ) from exc

        if response.status_code not in ok_status:
            message = _envelope_message(response)
            detail = f"：{message}" if message else ""
            raise UpstreamError(
                f"上游 {method} {path} 返回 HTTP {response.status_code}{detail}"
            )

        try:
            envelope = response.json()
        except ValueError as exc:
            raise UpstreamError(f"上游 {method} {path} 返回了非 JSON 响应。") from exc

        if not isinstance(envelope, dict):
            raise UpstreamError(f"上游 {method} {path} 响应信封格式异常。")

        code = envelope.get("code")
        if code not in ok_codes:
            message = envelope.get("message")
            raise UpstreamError(
                f"上游 {method} {path} 返回错误：code={code!r} message={message!r}"
            )

        data = envelope.get("data")
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise UpstreamError(f"上游 {method} {path} 的 data 字段不是对象。")
        return data

    async def list_pets(self, params: dict[str, Any]) -> dict[str, Any]:
        """``GET /api/v1/pets`` -> the unwrapped ``data`` object."""
        return await self._request("GET", "/api/v1/pets", params=params or None)

    async def create_pet(self, payload: dict[str, Any]) -> dict[str, Any]:
        """``POST /api/v1/pets`` -> the newly created pet (``data``)."""
        return await self._request(
            "POST",
            "/api/v1/pets",
            json_body=payload,
            ok_status=(200, 201),
            ok_codes=(200, 201),
        )

    async def delete_pet(self, pet_id: str) -> dict[str, Any]:
        """``DELETE /api/v1/pets/{id}`` -> ``data`` (used by tests/tooling)."""
        return await self._request("DELETE", f"/api/v1/pets/{pet_id}", ok_status=(200,))

    async def health(self) -> bool:
        """Best-effort liveness probe used by tests/tooling."""
        try:
            response = await self._client.get("/health")
        except httpx2.RequestError:
            return False
        return response.status_code == 200
