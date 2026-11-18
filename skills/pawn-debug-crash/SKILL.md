---
name: pawn-debug-crash
description: Diagnose SA-MP and open.mp server crashes and runtime errors from server_log.txt, log.txt, or pasted CrashDetect output (out-of-bounds, stack/heap collision, missing natives, plugin crashes, long callbacks) down to source lines and fixes. Use when the server crashes or logs Run time error, AMX backtrace, or Function not registered.
license: MIT
compatibility: Optional Python 3.8+ for pawnforge CLI / MCP log analysis and compiler verification.
metadata:
  author: POORSAKEN2
  version: "0.2.0"
---

# Debug a crash or runtime error

Log input: `log.txt` or `server_log.txt` in the server directory, or log text pasted by the user.

## Tool Resolution

1. **Pawn Forge MCP**: `analyze_log`, `project_info`, `api_lookup`, `compile`, `lint`.
2. **Standalone CLI**: `pawnforge <cmd> --json` (or `python scripts/pawnforge_exec.py <cmd> --json`, `python -m pawnforge <cmd> --json`, or `uvx --from git+https://github.com/POORSAKEN2/pawn-forge pawnforge <cmd> --json`).
3. **Fallback**: parse backtrace/log lines manually; suggest `pip install git+https://github.com/POORSAKEN2/pawn-forge.git`.

## Workflow

1. **Analyze log** with `analyze_log` (`source_root` = project root) or `pawnforge analyze-log <path> --source-root . --json` (pass `--text -` via stdin for pasted logs). Incidents come grouped by root cause and count; work highest count first.
2. **Inspect frames.** Open each frame's `file:line` and caller frames, and explain the cause in 1–2 sentences:
   - **Error 4 (out of bounds)**: identify array, index, and source. `65535` means `INVALID_PLAYER_ID`/`INVALID_VEHICLE_ID` reached a lookup; `-1` means an unchecked failed search; `index == size` means off-by-one.
   - **Error 3 (stack/heap collision)**: large locals or deep recursion; check `compile` / `pawnforge compile` `stack` estimate.
   - **Error 19 / missing natives**: plugin/component not loaded or mismatched with its include. Inspect `config.json` (`pawn.legacy_plugins`) / `server.cfg` (`plugins`) and `plugin_failures`.
   - **Server crash (`suspect_module`)**: plugin fault from bad arguments or plugin/include version mismatch.
   - **Long callback**: unbounded loop, blocking `mysql_query`, or file I/O in the top frame.
3. **Missing `file:line`?** The script was compiled without debug symbols or CrashDetect is missing: instruct the user to compile with `-d3` (default in `compile` / `pawnforge compile`) and load CrashDetect, then reproduce.
4. **Fix at the root cause** (validate the ID or index where it enters, not only at the crash line). Compile until clean (`pawn-build`) and `lint` changed files (`pawnforge lint <file> --json`) to catch sibling occurrences.
5. **Report** each root cause, the fix applied, and verification steps (reproduce or run `pawn-test`).
