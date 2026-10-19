#!/usr/bin/env python3
"""PostToolUse hook: lint the Pawn lines Claude just wrote and feed findings back.

Only findings on the changed lines are reported, so editing a large legacy
file does not dump every pre-existing issue on each edit. Never blocks and
never fails the tool call: any problem here exits 0 silently.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

PAWN_EXT = (".pwn", ".inc", ".p")
MAX_REPORTED = 12


def changed_ranges(text: str, tool: str, ti: dict) -> list[tuple[int, int]] | None:
    """Line ranges (1-based, inclusive) touched by the edit; None means whole file."""
    if tool == "Write":
        return None
    news = []
    if tool == "MultiEdit":
        news = [e.get("new_string", "") for e in ti.get("edits", []) if isinstance(e, dict)]
    else:
        news = [ti.get("new_string", "")]
    ranges = []
    for new in news:
        if not new or not new.strip():
            continue
        start = 0
        while True:
            i = text.find(new, start)
            if i < 0:
                break
            a = text.count("\n", 0, i) + 1
            b = a + new.count("\n")
            ranges.append((a, b))
            start = i + max(1, len(new))
    return ranges


def main() -> int:
    if os.environ.get("CLAUDE_PLUGIN_OPTION_LINT_ON_EDIT", "true").strip().lower() in ("false", "0", "no", "off"):
        return 0
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    tool = payload.get("tool_name", "")
    ti = payload.get("tool_input") or {}
    path = ti.get("file_path") or ti.get("path")
    if not path or not str(path).lower().endswith(PAWN_EXT):
        return 0
    p = Path(path)
    if not p.is_absolute():
        p = Path(payload.get("cwd") or os.getcwd()) / p
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    ranges = changed_ranges(text, tool, ti)
    if ranges is not None and not ranges:
        return 0

    from pawnforge.lint import lint_source  # imported late: keep the no-op path fast

    findings = lint_source(text, str(p), min_severity="warning")
    if ranges is not None:
        findings = [f for f in findings if any(a <= f["line"] <= b for a, b in ranges)]
    if not findings:
        return 0
    findings.sort(key=lambda f: (0 if f["severity"] == "error" else 1, f["line"]))
    lines = [f"pawn-forge lint found {len(findings)} issue(s) in the code just written to {p.name}:"]
    for f in findings[:MAX_REPORTED]:
        lines.append(f"- line {f['line']} [{f['rule']} {f['severity']}] {f['message']} Fix: {f['fix']}")
    if len(findings) > MAX_REPORTED:
        lines.append(f"- ...and {len(findings) - MAX_REPORTED} more (run the pawn-forge lint tool on the file).")
    lines.append("Fix these before moving on, or justify a deliberate exception with "
                 "`// pawnforge-ignore <RULE>` on that line. Then compile with the pawn-forge compile tool.")
    out = {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "\n".join(lines)}}
    sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
