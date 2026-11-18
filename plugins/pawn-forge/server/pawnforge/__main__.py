"""Allow running the standalone CLI via `python -m pawnforge`."""
from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
