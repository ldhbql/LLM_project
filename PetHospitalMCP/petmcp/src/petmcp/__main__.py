"""stdio entrypoint: ``python -m petmcp``.

Protocol frames are the only thing written to stdout; all logging goes to
stderr. The process exits when the client closes stdin (the SDK's stdio
transport turns EOF into a clean shutdown).
"""

from __future__ import annotations

import argparse
import logging
import sys

import anyio

from . import __version__
from .config import DEFAULT_API_BASE, DEFAULT_TIMEOUT, ServerConfig
from .server import build_server
from .transport import run_stdio
from .upstream import PetHospitalClient


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="petmcp",
        description="宠物医院 MCP Server（stdio 传输，MCP 协议 2026-07-28，MVP：list_pets）",
    )
    parser.add_argument(
        "--api",
        default=None,
        help=f"上游 REST 基址，默认 {DEFAULT_API_BASE}（也可用环境变量 PET_API_URL）",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"上游 HTTP 超时秒数，默认 {DEFAULT_TIMEOUT}",
    )
    parser.add_argument("--verbose", action="store_true", help="输出调试日志到 stderr")
    parser.add_argument(
        "--modern-only",
        action="store_true",
        help="只接受 2026-07-28 及以后的无状态请求，拒绝 legacy initialize 握手"
        "（默认双代：同时兼容旧版 MCP 客户端，如 opencode 1.18.x）",
    )
    parser.add_argument("--version", action="version", version=__version__)
    return parser.parse_args(argv)


async def _run(config: ServerConfig, modern_only: bool) -> None:
    client = PetHospitalClient(config)
    try:
        server = build_server(client, config)
        await run_stdio(server, modern_only=modern_only)
    finally:
        await client.aclose()


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = ServerConfig.from_env(api_base=args.api, timeout=args.timeout)
    anyio.run(_run, config, args.modern_only)


if __name__ == "__main__":
    main()
