#!/usr/bin/env python3
"""SessionStart hook: in a Pawn project, remind Claude which tools exist.

Prints nothing (and costs no context) outside Pawn projects.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def is_pawn_project(root: Path) -> str | None:
    try:
        if (root / "pawn.json").exists() or (root / "pawn.yaml").exists():
            return "sampctl package"
        for sub in ("gamemodes", "filterscripts", "src", "."):
            d = root / sub
            if d.is_dir() and any(d.glob("*.pwn")):
                return "open.mp" if (root / "config.json").exists() or (root / "qawno").exists() else "Pawn"
        if (root / "qawno").is_dir() or (root / "pawno").is_dir():
            return "server"
    except OSError:
        return None
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd())
    kind = is_pawn_project(root)
    if not kind:
        return 0
    print(
        f"[pawn-forge] Pawn ({kind}) project detected. The pawn-forge MCP tools are available: `compile` after every "
        "Pawn change (iterate until clean), `lint` on changed files, `lookup` for any vehicle/skin/weapon/interior/"
        "animation ID, `api_lookup` for exact native signatures, `analyze_log` for crashes, `project_info` for layout. "
        "Workflows: /pawn-forge:build, /pawn-forge:audit, /pawn-forge:migrate-openmp, /pawn-forge:debug-crash, "
        "/pawn-forge:textdraw, /pawn-forge:modernize-storage, /pawn-forge:test."
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
