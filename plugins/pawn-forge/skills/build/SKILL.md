---
description: Compile a Pawn gamemode, filterscript or include with the real Pawn compiler and fix every error and warning until the build is clean. Use when asked to build, compile, or fix compiler errors/warnings in SA-MP or open.mp code.
argument-hint: "[file.pwn] [keep]"
allowed-tools: mcp__plugin_pawn-forge_pawn__compile mcp__plugin_pawn-forge_pawn__project_info mcp__plugin_pawn-forge_pawn__api_lookup mcp__plugin_pawn-forge_pawn__lookup mcp__plugin_pawn-forge_pawn__lint
---

# Build until clean

Target: `$ARGUMENTS` (a .pwn path, optionally followed by `keep` to keep the .amx).

1. **Resolve the target.** If no file was given, call `project_info` on the working directory and use
   `main_script`. If several gamemodes exist and none was named, ask which one.
2. **Compile** with `compile` (`output: "alongside"` only if `keep` was passed, otherwise the default temp output).
   - No compiler found: say so, show what was searched, and offer `install_compiler` (it downloads from GitHub, so
     ask first). Do not continue without a compiler.
   - `fatal 100` (include not found): check `project_info.include_dirs`; for sampctl projects suggest
     `sampctl ensure`; otherwise pass `includes`.
   - Errors only inside third-party includes: try `compat: true` for legacy SA-MP 0.3.7 headers before touching code.
3. **Fix, recompile, repeat** (at most 8 rounds; stop and report if the count stops falling):
   - Errors first, top-down. The first error often causes the rest; recompile after fixing it.
   - Then warnings in the project's own files. Report, but never edit, warnings that live in third-party includes.
   - Use each diagnostic's `hint`. For `017`, `202`, `025`, `035` and `213` check the real signature with
     `api_lookup` (pass `project_dir`) instead of guessing.
   - Fix causes, not symptoms. Never silence diagnostics with `#pragma warning disable`, `#pragma unused` on code
     that is genuinely dead, or `_:` tag casts. A tag mismatch means the wrong constant or type is being used.
   - Keep each fix minimal and in the project's existing style.
4. **Lint the files you changed** with `lint` (`min_severity: "warning"`) and fix anything your edits introduced.
5. **Report** briefly: final status (`ok`/`clean`), what you fixed (grouped), the stack estimate if it carries a
   warning, and anything that needs the user's decision. If `keep` was used, give the .amx path.
