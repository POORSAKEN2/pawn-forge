---
description: Convert a raw TextDraw editor export (Zamaroht/iTD/nTD style TextDrawCreate and CreatePlayerTextDraw code) into a clean, leak-free Pawn module with arrays, named indices and Create/Destroy/Show/Hide functions, then compile it. Use when the user pastes TextDraw editor output or asks to clean up, refactor or build a HUD/TextDraw UI.
argument-hint: "[export-file] [Prefix]"
allowed-tools: mcp__plugin_pawn-forge_pawn__convert_textdraws mcp__plugin_pawn-forge_pawn__compile mcp__plugin_pawn-forge_pawn__project_info
---

# TextDraw export to module

Input: `$ARGUMENTS` - an export file and optionally a module prefix; or the export pasted in the conversation.

1. Pick a prefix: the one given, else a short PascalCase name from what the TextDraws show (e.g. `Speedo`, `Hud`,
   `Login`). Target `openmp` unless `project_info` says the project is SA-MP.
2. `convert_textdraws` with the export (`file` or `code`), `prefix`, `target`, and `ysi_hooks: true` only if the
   project already uses YSI.
3. Show the `warnings` (off-canvas positions, selectable TextDraws without TextSize, limits) and fix them in the
   export or ask the user how they want them handled; then convert again.
4. Write the module: `includes/<prefix_lowercase>_td.inc` (or the project's include folder) via `write_to`. It
   refuses to overwrite; pick another name or ask.
5. Verify it compiles: `compile` with `code` = `#include <open.mp>` + `#include "<module>"` + `main(){}`, passing the
   module's directory in `includes`. Fix anything reported.
6. Wire it in (with the user's go-ahead): create in `OnGameModeInit` / `OnPlayerConnect`, destroy in
   `OnGameModeExit` / `OnPlayerDisconnect` (skip if `ysi_hooks` was used), show/hide where the UI appears. Update
   individual TextDraws through the generated `<Prefix>_GetPlayerTD(playerid, INDEX)` / `<Prefix>_GetGlobalTD(INDEX)`.
7. Remind the user: TextDraws live on a fixed 640x448 virtual canvas that scales with the screen; "responsive" means
   keeping elements inside the canvas and anchoring them with alignment, not pixel maths.
