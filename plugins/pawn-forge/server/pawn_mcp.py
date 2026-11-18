#!/usr/bin/env python3
"""pawn-forge MCP server (stdio, JSON-RPC 2.0, newline-delimited).

Standard library only: requires Python 3.8+ and nothing else.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pawnforge.mcp_entry import INSTRUCTIONS, SUPPORTED_PROTOCOLS, handle, main  # noqa: E402, F401


if __name__ == "__main__":
    main()
