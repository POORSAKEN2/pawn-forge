"""pawn-forge MCP server entry point (stdio, JSON-RPC 2.0, newline-delimited).

Standard library only: requires Python 3.8+ and nothing else.
"""
from __future__ import annotations

import json
import sys
import traceback
from typing import Any, TextIO

from . import __version__
from .tools import call_tool, list_tools

SUPPORTED_PROTOCOLS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
INSTRUCTIONS = (
    "Deterministic toolchain for Pawn (SA-MP / open.mp). Rules: compile every Pawn change with `compile` and "
    "iterate until clean before presenting code; run `lint` on changed files; use `lookup` for any vehicle, "
    "skin, weapon, interior or animation ID and `api_lookup` for any native signature instead of recalling "
    "them; use `analyze_log` for crash/log questions. Start in an unfamiliar project with `project_info`."
)


def _send(out: TextIO, msg: dict[str, Any]) -> None:
    out.write(json.dumps(msg, ensure_ascii=False, separators=(",", ":")) + "\n")
    out.flush()


def _result(out: TextIO, id_: Any, res: Any) -> None:
    _send(out, {"jsonrpc": "2.0", "id": id_, "result": res})


def _error(out: TextIO, id_: Any, code: int, message: str) -> None:
    _send(out, {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}})


def handle(msg: dict[str, Any], out: TextIO | None = None) -> None:
    target = out if out is not None else sys.stdout
    method = msg.get("method")
    id_ = msg.get("id")
    is_request = "id" in msg
    params = msg.get("params") or {}

    if method == "initialize":
        requested = params.get("protocolVersion")
        version = requested if requested in SUPPORTED_PROTOCOLS else SUPPORTED_PROTOCOLS[1]
        _result(target, id_, {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "pawn-forge", "title": "Pawn Forge", "version": __version__},
            "instructions": INSTRUCTIONS,
        })
    elif method == "ping":
        _result(target, id_, {})
    elif method == "tools/list":
        _result(target, id_, {"tools": list_tools()})
    elif method == "tools/call":
        name = params.get("name", "")
        args = params.get("arguments") or {}
        try:
            out_res = call_tool(name, args)
            text = json.dumps(out_res, ensure_ascii=False, separators=(",", ":"), default=str)
            is_err = isinstance(out_res, dict) and out_res.get("ok") is False
            _result(target, id_, {"content": [{"type": "text", "text": text}], "isError": bool(is_err)})
        except (KeyError, ValueError, TypeError) as exc:
            _result(target, id_, {"content": [{"type": "text", "text": f"Invalid call: {exc}"}], "isError": True})
        except Exception as exc:  # report, never crash the server
            traceback.print_exc(file=sys.stderr)
            _result(target, id_, {"content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}], "isError": True})
    elif method and method.startswith("notifications/"):
        return
    elif is_request:
        _error(target, id_, -32601, f"Method not found: {method}")


def main() -> None:
    out = sys.stdout
    if hasattr(out, "reconfigure"):
        try:
            out.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stdin, "reconfigure"):
        try:
            sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    sys.stdout = sys.stderr  # nothing but protocol messages may reach the real stdout
    try:
        for raw in sys.stdin:
            raw = raw.strip()
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                _error(out, None, -32700, "Parse error")
                continue
            batch = msg if isinstance(msg, list) else [msg]
            for m in batch:
                if isinstance(m, dict):
                    try:
                        handle(m, out)
                    except Exception as exc:
                        traceback.print_exc(file=sys.stderr)
                        if "id" in m:
                            _error(out, m.get("id"), -32603, f"Internal error: {exc}")
    finally:
        sys.stdout = out


if __name__ == "__main__":
    main()
