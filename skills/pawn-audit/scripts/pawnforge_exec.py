#!/usr/bin/env python3
"""Zero-dependency bootstrapper for the pawnforge CLI."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

INSTALL_CMD = "pip install git+https://github.com/POORSAKEN2/pawn-forge.git"


def _find_server_dir() -> Path | None:
    home = Path(os.environ["HOME"]) if os.environ.get("HOME") else Path.home()
    here = Path(__file__).resolve()
    candidates = [
        Path.cwd() / ".agents" / "plugins" / "pawn-forge" / "server",
        Path.cwd() / "plugins" / "pawn-forge" / "server",
        home / ".gemini" / "config" / "plugins" / "pawn-forge" / "server",
    ]
    if len(here.parents) > 3:
        candidates.append(here.parents[3] / "server")
    for base in candidates:
        if (base / "pawnforge" / "cli.py").is_file():
            return base
    claude_plugins = home / ".claude" / "plugins"
    if claude_plugins.is_dir():
        for cli_file in claude_plugins.rglob("cli.py"):
            if cli_file.parent.name == "pawnforge" and cli_file.is_file():
                return cli_file.parent.parent
    return None


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    exe = shutil.which("pawnforge")
    if exe:
        return subprocess.run([exe, *args]).returncode
    if importlib.util.find_spec("pawnforge") is not None:
        return subprocess.run([sys.executable, "-m", "pawnforge", *args]).returncode
    server_dir = _find_server_dir()
    if server_dir is not None:
        env = dict(os.environ)
        prev = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{server_dir}{os.pathsep}{prev}" if prev else str(server_dir)
        return subprocess.run([sys.executable, "-m", "pawnforge", *args], env=env).returncode
    print(json.dumps({
        "ok": False,
        "error": "pawnforge CLI not installed",
        "install": INSTALL_CMD,
    }))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
