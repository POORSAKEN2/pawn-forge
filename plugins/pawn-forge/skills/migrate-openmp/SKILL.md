---
name: migrate-openmp
description: Migrate a SA-MP 0.3.7 gamemode or filterscript to open.mp (includes, renamed/deprecated natives, tagged constants, callback headers, plugins to components) and compile clean against open.mp includes. Use when asked to port, upgrade, or convert a SA-MP script or server to open.mp.
license: MIT
compatibility: Optional Python 3.8+ for pawnforge CLI / MCP migration and compiler tools.
metadata:
  author: POORSAKEN2
  version: "0.2.0"
argument-hint: "[file.pwn | directory]"
---

# Migrate to open.mp

Target: `.pwn` file or project directory (default: main script and its local includes).

## Tool Resolution

1. **Pawn Forge MCP**: `project_info`, `migrate_openmp`, `compile`, `api_lookup`, `lint`.
2. **Standalone CLI**: `pawnforge <cmd> --json` (or `python scripts/pawnforge_exec.py <cmd> --json`, `python -m pawnforge <cmd> --json`, or `uvx --from git+https://github.com/POORSAKEN2/pawn-forge pawnforge <cmd> --json`).
3. **Fallback**: manually replace `<a_samp>` / renamed natives / tags and compile with open.mp's `pawncc`; suggest `pip install git+https://github.com/POORSAKEN2/pawn-forge.git`.

## Workflow

1. **Survey** with `project_info` / `pawnforge info <dir> --json`: confirm platform, plugins (`server.cfg` / `plugins/`), libraries, and project vs third-party includes (replace third-party libraries with open.mp-compatible releases rather than editing them).
2. **Dry run** each project file with `migrate_openmp` (`write: "none"`) / `pawnforge migrate <file> --write none --json`. Summarise mechanical safe changes and manual items per file.
3. **Apply** once confirmed (or immediately if requested): `write: "in_place"` / `--write in_place` creates a `<file>.samp.bak` backup; use `write: "copy"` / `--write copy` to leave originals untouched.
4. **Resolve manual items**:
   - `GetPlayerPoolSize`/`GetVehiclePoolSize` loops -> `i < MAX_PLAYERS` or `foreach (new i : Player)` (watch `<=` bounds).
   - Deprecated natives without direct aliases -> check replacement via `api_lookup` (`platform="open.mp"`) / `pawnforge api --name <sym> --platform open.mp --json`.
   - YSI 4 includes -> YSI 5 paths (`YSI_Coding\y_hooks`, etc.).
5. **Compile** against open.mp includes (`qawno/include`) until clean using `build`. Warning 213 means a literal was passed where a tagged constant belongs—fix the constant, never `_:` cast it away.
6. **Server-side steps** (inform user; do not edit server config without asking):
   - Convert `server.cfg` to `config.json` via `./omp-server --dump-config`.
   - Place component builds (`Pawn.CMD` `-omp`, `Pawn.RakNet`, `sscanf` 2.13.8+, `discord-connector`, `sampvoice`) in `components/`; keep others in `plugins/` under `pawn.legacy_plugins`.
   - YSF is unnecessary; replace FCNPC with the NPC component and SKY with Pawn.RakNet.
7. **Verify**: `lint` migrated files (`pawnforge lint <path> --json`); offer `test` if a local open.mp server exists.
8. **Report**: files changed, manual decisions, and remaining server-side steps.
