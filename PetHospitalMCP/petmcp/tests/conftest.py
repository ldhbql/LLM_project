"""Shared test fixtures and a stdio harness that drives the real server process."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
from typing import Any

import pytest

from petmcp.protocol import client_meta


class StdioSession:
    """Drive ``python -m petmcp`` over real stdin/stdout pipes."""

    def __init__(self, env: dict[str, str] | None = None, args: list[str] | None = None) -> None:
        full_env = dict(os.environ)
        if env:
            full_env.update(env)
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "petmcp", *(args or [])],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
            env=full_env,
        )
        self._lines: "queue.Queue[str]" = queue.Queue()
        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()

    def _pump(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            self._lines.put(line)

    def send_raw(self, payload: dict[str, Any]) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

    def call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        meta: dict[str, Any] | None = None,
        request_id: int = 1,
        timeout: float = 20.0,
    ) -> dict[str, Any]:
        body = dict(params or {})
        if meta is not None:
            body["_meta"] = meta
        self.send_raw({"jsonrpc": "2.0", "id": request_id, "method": method, "params": body})
        try:
            line = self._lines.get(timeout=timeout)
        except queue.Empty as exc:  # pragma: no cover - only on a hung server
            raise AssertionError(f"timed out waiting for a response to {method!r}") from exc
        return json.loads(line)

    def recv(self, timeout: float = 20.0) -> dict[str, Any]:
        """Read the next server message (request, notification or response)."""
        try:
            line = self._lines.get(timeout=timeout)
        except queue.Empty as exc:  # pragma: no cover - only on a hung server
            raise AssertionError("timed out waiting for a server message") from exc
        return json.loads(line)

    def close(self) -> None:
        if self.proc.stdin:
            self.proc.stdin.close()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover
            self.proc.kill()
            self.proc.wait(timeout=5)

    def __enter__(self) -> "StdioSession":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


@pytest.fixture
def stdio_server():
    session = StdioSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def make_stdio():
    """Factory for sessions with custom args/env, closed automatically."""
    sessions: list[StdioSession] = []

    def factory(**kwargs: object) -> StdioSession:
        session = StdioSession(**kwargs)  # type: ignore[arg-type]
        sessions.append(session)
        return session

    yield factory
    for session in sessions:
        session.close()


@pytest.fixture
def modern_meta() -> dict[str, Any]:
    return client_meta()
