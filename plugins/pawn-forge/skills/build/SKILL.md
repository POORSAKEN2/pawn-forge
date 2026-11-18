---
name: build
description: Compile a Pawn (.pwn/.inc) gamemode, filterscript, or include with pawncc and fix every error and warning until the build is clean. Use when asked to build, compile, or fix compiler errors or warnings in SA-MP 0.3.7 or open.mp code.
license: MIT
compatibility: Optional Python 3.8+ for pawnforge CLI / MCP verification and pawncc 3.10.x compiler.
metadata:
  author: POORSAKEN2
  version: "0.2.0"
argument-hint: "[file.pwn] [keep]"
---

# Build until clean

Target: a `.pwn` path (optionally `keep` to retain the `.amx` alongside the source).

## Tool Resolution

1. **Pawn Forge MCP**: `project_info`, `compile`, `install_compiler`, `api_lookup`, `lookup`, `lint`.
2. **Standalone CLI**: `pawnforge <cmd> --json` (or `python scripts/pawnforge_exec.py <cmd> --json`, `python -m pawnforge <cmd> --json`, or `uvx --from git+https://github.com/POORSAKEN2/pawn-forge pawnforge <cmd> --json`).
3. **Fallback**: run `pawncc` directly (`-;+ -(+ -d3`); suggest `pip install git+https://github.com/POORSAKEN2/pawn-forge.git`.

## Workflow

1. **Resolve target.** If no file was given, run `project_info` / `pawnforge info . --json` and use `main_script`. If multiple gamemodes exist and none was named, ask which one.
2. **Compile** with `compile` / `pawnforge compile <file> --json` (pass `output: "alongside"` / `--output alongside` only if `keep` is requested).
   - No compiler found: report searched locations and ask before running `install_compiler` / `pawnforge install-compiler`. Do not skip compilation silently.
   - `fatal 100` (include not found): check `project_info.include_dirs`; for sampctl projects suggest `sampctl ensure`; otherwise pass `includes` / `--includes`.
   - Errors only inside third-party includes: retry with `compat: true` / `--compat` (`-Z`) for legacy SA-MP 0.3.7 headers before touching code.
3. **Fix, recompile, repeat** (max 8 rounds; stop and report if the count stops falling):
   - Errors first, top-down—the first error often triggers the rest.
   - Then warnings in the project's own files. Report, never edit, warnings inside third-party includes.
   - Use each diagnostic's `hint`. For `017`, `202`, `025`, `035`, or `213`, check the real signature with `api_lookup` / `pawnforge api --name <sym> --platform <auto|open.mp|sa-mp> --project-dir . --json`.
   - Fix causes, not symptoms: never silence diagnostics with `#pragma warning disable`, fake `#pragma unused`, or `_:` tag casts. Keep fixes minimal and consistent with project style.
4. **Lint changed files** with `lint` (`min_severity: "warning"`) / `pawnforge lint <file> --min-severity warning --json` and fix any issues introduced.
5. **Report** briefly: final status (`ok`/`clean`), grouped fixes, `stack` warning if present, unresolved third-party warnings, and `.amx` path if `keep` was requested.
