#!/usr/bin/env python3
"""pawn-forge MCP server (stdio, JSON-RPC 2.0, newline-delimited).

Standard library only: requires Python 3.8+ and nothing else.
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pawnforge import __version__  # noqa: E402
from pawnforge.tools import call_tool, list_tools  # noqa: E402

SUPPORTED_PROTOCOLS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
INSTRUCTIONS = (
    "Deterministic toolchain for Pawn (SA-MP / open.mp). Rules: compile every Pawn change with `compile` and "
    "iterate until clean before presenting code; run `lint` on changed files; use `lookup` for any vehicle, "
    "skin, weapon, interior or animation ID and `api_lookup` for any native signature instead of recalling "
    "them; use `analyze_log` for crash/log questions. Start in an unfamiliar project with `project_info`."
)

_out = sys.stdout
sys.stdout = sys.stderr  # nothing but protocol messages may reach the real stdout


def send(msg: dict) -> None:
    _out.write(json.dumps(msg, ensure_ascii=False, separators=(",", ":")) + "\n")
    _out.flush()


def result(id_, res) -> None:
    send({"jsonrpc": "2.0", "id": id_, "result": res})


def error(id_, code: int, message: str) -> None:
    send({"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}})


def handle(msg: dict) -> None:
    method = msg.get("method")
    id_ = msg.get("id")
    is_request = "id" in msg
    params = msg.get("params") or {}

    if method == "initialize":
        requested = params.get("protocolVersion")
        version = requested if requested in SUPPORTED_PROTOCOLS else SUPPORTED_PROTOCOLS[1]
        result(id_, {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "pawn-forge", "title": "Pawn Forge", "version": __version__},
            "instructions": INSTRUCTIONS,
        })
    elif method == "ping":
        result(id_, {})
    elif method == "tools/list":
        result(id_, {"tools": list_tools()})
    elif method == "tools/call":
        name = params.get("name", "")
        args = params.get("arguments") or {}
        try:
            out = call_tool(name, args)
            text = json.dumps(out, ensure_ascii=False, separators=(",", ":"), default=str)
            is_err = isinstance(out, dict) and out.get("ok") is False
            result(id_, {"content": [{"type": "text", "text": text}], "isError": bool(is_err)})
        except (KeyError, ValueError, TypeError) as exc:
            result(id_, {"content": [{"type": "text", "text": f"Invalid call: {exc}"}], "isError": True})
        except Exception as exc:  # report, never crash the server
            traceback.print_exc(file=sys.stderr)
            result(id_, {"content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}], "isError": True})
    elif method and method.startswith("notifications/"):
        return
    elif is_request:
        error(id_, -32601, f"Method not found: {method}")


def main() -> None:
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            error(None, -32700, "Parse error")
            continue
        batch = msg if isinstance(msg, list) else [msg]
        for m in batch:
            if isinstance(m, dict):
                try:
                    handle(m)
                except Exception as exc:
                    traceback.print_exc(file=sys.stderr)
                    if "id" in m:
                        error(m.get("id"), -32603, f"Internal error: {exc}")


if __name__ == "__main__":
    main()
