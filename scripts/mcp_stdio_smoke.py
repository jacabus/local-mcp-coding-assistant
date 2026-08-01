#!/usr/bin/env python3
"""Fresh stdio MCP smoke against current server.py (proves MCP path after code changes)."""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "medium_review_fixture.py"
PASS_BAR_SECONDS = 45.0


async def run() -> None:
    if not FIXTURE_PATH.is_file():
        raise RuntimeError(f"missing fixture {FIXTURE_PATH}")
    code = FIXTURE_PATH.read_text(encoding="utf-8")
    venv_python = REPO_ROOT / ".venv" / "bin" / "python"
    if not venv_python.is_file():
        raise RuntimeError(f"missing interpreter {venv_python}")

    env = dict(os.environ)
    env["VIRTUAL_ENV"] = str(REPO_ROOT / ".venv")
    env["PATH"] = str(REPO_ROOT / ".venv" / "bin") + os.pathsep + env.get("PATH", "")
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )

    params = StdioServerParameters(
        command=str(venv_python),
        args=[str(REPO_ROOT / "src" / "server.py")],
        cwd=str(REPO_ROOT),
        env=env,
    )

    started = time.perf_counter()
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "local_code_review",
                {"code": code, "context": "mcp_stdio_smoke"},
            )
    elapsed = time.perf_counter() - started
    text = "\n".join(getattr(block, "text", str(block)) for block in result.content)
    preview = text.replace("\n", " ").strip()
    print(f"elapsed_sec={elapsed:.2f}")
    print(f"preview={preview[:220]}")
    if getattr(result, "isError", False) or not preview:
        raise RuntimeError("MCP tool returned empty or error result")
    if elapsed > PASS_BAR_SECONDS:
        raise RuntimeError(f"elapsed {elapsed:.2f}s exceeds pass bar {PASS_BAR_SECONDS:.0f}s")
    print(f"PASS: fresh MCP stdio medium review under {PASS_BAR_SECONDS:.0f}s")


def main() -> int:
    try:
        asyncio.run(run())
    except Exception as exc:
        print(f"FAIL: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
