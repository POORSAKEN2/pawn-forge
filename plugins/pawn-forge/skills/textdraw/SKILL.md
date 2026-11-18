---
name: textdraw
description: Convert raw TextDraw editor exports (Zamaroht/iTD/nTD TextDrawCreate and CreatePlayerTextDraw) into a clean, leak-free Pawn module with arrays, named indices, and Create/Destroy/Show/Hide helpers, then compile it. Use when given TextDraw exports or asked to refactor or build a TextDraw HUD/UI.
license: MIT
compatibility: Optional Python 3.8+ for pawnforge CLI / MCP tools and pawncc.
metadata:
  author: POORSAKEN2
  version: "0.2.0"
argument-hint: "[export-file] [Prefix]"
---

# TextDraw export to module

Input: an export file or pasted TextDraw code, plus an optional PascalCase module prefix.

## Tool Resolution

1. **Pawn Forge MCP**: `project_info`, `convert_textdraws`, `compile`.
2. **Standalone CLI**: `pawnforge <cmd> --json` (or `python scripts/pawnforge_exec.py <cmd> --json`, `python -m pawnforge <cmd> --json`, or `uvx --from git+https://github.com/POORSAKEN2/pawn-forge pawnforge <cmd> --json`).
3. **Fallback**: refactor manually into `enum` + `Text:`/`PlayerText:` arrays and compile with `pawncc`; suggest `pip install git+https://github.com/POORSAKEN2/pawn-forge.git`.

## Workflow

1. **Pick prefix & target.** Use the requested PascalCase prefix or derive a short name (`Speedo`, `Hud`, `Login`). Target `openmp` unless `project_info` / `pawnforge info . --json` reports `sa-mp`.
2. **Convert** with `convert_textdraws` (`file` or `code`, `prefix`, `target`, and `ysi_hooks: true` only if the project already uses YSI) or `pawnforge textdraw [file] --prefix <Prefix> --target <openmp|samp> [--ysi-hooks] --json`.
3. **Review `warnings`** (off-canvas coordinates, selectable TextDraws missing `TextSize`, pool limits). Fix them in the export or confirm handling with the user, then convert again.
4. **Write module** to `includes/<prefix_lowercase>_td.inc` (or the project's include folder) via `write_to` / `--write-to`. It refuses to overwrite existing files—choose another path or ask.
5. **Verify compilation** using `compile` / `pawnforge compile --code - --includes <dir> --json` with `#include <open.mp>` (or `<a_samp>`) + `#include "<module>"` + `main(){}`, fixing any diagnostics.
6. **Wire lifecycle** (with the user's go-ahead): create in `OnGameModeInit` / `OnPlayerConnect`, destroy in `OnGameModeExit` / `OnPlayerDisconnect` (skip if `ysi_hooks` was used), and show/hide where the UI appears. Update elements via `<Prefix>_GetPlayerTD(playerid, INDEX)` / `<Prefix>_GetGlobalTD(INDEX)`.
7. **Canvas note:** TextDraws render on a fixed `640x448` virtual canvas that scales with the screen; responsive layout means staying within bounds and anchoring via alignment, not pixel maths.
