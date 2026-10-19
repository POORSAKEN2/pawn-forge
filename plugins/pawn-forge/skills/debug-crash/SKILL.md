---
description: Diagnose SA-MP / open.mp server crashes and runtime errors from server_log.txt, log.txt or pasted CrashDetect output - array index out of bounds, stack/heap collision, missing natives, plugin crashes, long callbacks - down to the source line and a fix. Use when the server crashes, prints "Run time error", "AMX backtrace", "Function not registered", or behaves erratically.
argument-hint: "[log path]"
allowed-tools: mcp__plugin_pawn-forge_pawn__analyze_log mcp__plugin_pawn-forge_pawn__project_info mcp__plugin_pawn-forge_pawn__api_lookup mcp__plugin_pawn-forge_pawn__compile mcp__plugin_pawn-forge_pawn__lint
---

# Debug a crash or runtime error

Log: `$ARGUMENTS` (default: `log.txt` or `server_log.txt` in the server directory; or text the user pasted).

1. `analyze_log` with `source_root` set to the project root so frames get source context. Incidents come grouped by
   root cause with counts; work through them in order of count.
2. For each incident, open the frame's file at the reported line (and the caller frames) and explain the actual
   cause in one or two sentences:
   - **Error 4, out of bounds**: which index, which array, where the bad value came from. Index 65535 means
     `INVALID_PLAYER_ID`/`INVALID_VEHICLE_ID` reached a lookup; -1 means a failed search was used unchecked;
     index == size means an off-by-one.
   - **Error 3, stack/heap collision**: large locals or recursion; check `compile`'s `stack` estimate.
   - **Error 19 / missing natives**: the plugin providing them is not loaded or its version does not match the
     include. Check `config.json` `pawn.legacy_plugins` / `server.cfg plugins` and `plugin_failures`.
   - **Server crashed** with `suspect_module`: a plugin faulted, usually from bad arguments or a version mismatch
     between the plugin and its include.
   - **Long callback**: an unbounded loop, blocking `mysql_query`, or file I/O in the top frame.
3. If frames have no file:line, the script was built without debug info or CrashDetect is not loaded: tell the user
   to compile with `-d3` (the `compile` tool does) and load crashdetect, then reproduce.
4. **Fix** the code at the root cause (validate the index or ID at its source, not just at the crash line), then
   `compile` until clean and `lint` the changed files. Search for the same pattern elsewhere (`lint` rules for the
   class of bug) and mention other occurrences.
5. Report: each root cause, the fix, and how to confirm (reproduce steps, or the `test` workflow).
