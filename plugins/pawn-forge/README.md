# Pawn Forge

A Claude Code plugin that turns Claude into a SA-MP / open.mp engineer instead of a code guesser.

General models write Pawn the way 2008-2014 forum tutorials did: `strtok` commands, `dini` accounts,
`format(query, ..., "'%s'")` SQL, `new string[256]`, invented vehicle IDs and animation names. Pawn Forge puts
deterministic tools in the loop so Claude **compiles** what it writes, **lints** it for the defects that actually crash
or compromise servers, and **looks up** IDs and signatures from the real open.mp data and library headers.

## What you get

| Component | What it does |
|---|---|
| **MCP server** (11 tools, Python stdlib only) | Compiler bridge, static analysis, crash-log triage, ID and API lookup, open.mp migration, TextDraw conversion, headless server runs |
| **Skill: pawn-standards** | Loaded automatically for `.pwn`/`.inc` work: modern practice for strings, MySQL R41, SQLite, YSI 5, Streamer, Pawn.CMD, sscanf, open.mp. Every snippet in it is compile-tested. |
| **Workflows** | `/pawn-forge:build`, `/pawn-forge:audit`, `/pawn-forge:migrate-openmp`, `/pawn-forge:debug-crash`, `/pawn-forge:textdraw`, `/pawn-forge:modernize-storage`, `/pawn-forge:test` |
| **Agents** | `pawn-auditor` (read-only, large audits), `pawn-build-fixer` (compile until clean) |
| **Hooks** | Lints the lines Claude just edited in Pawn files and feeds findings back; announces the toolchain when a session starts in a Pawn project |

## Install

```text
/plugin marketplace add POORSAKEN2/pawn-forge
/plugin install pawn-forge@pawn-forge
```

or from a shell: `claude plugin marketplace add POORSAKEN2/pawn-forge` then `claude plugin install pawn-forge@pawn-forge`.
To try it from a local checkout: `claude --plugin-dir ./plugins/pawn-forge`.

### Requirements

- **Python 3.8+** on PATH. No packages to install.
  On Windows set the plugin's *Python command* option to `py` (or `python`).
- **A Pawn compiler** (pawncc 3.10.x). Found automatically in the project's `qawno/` or `pawno/`, on PATH, through
  the *pawncc path* option, or installed on request by the `install_compiler` tool (open.mp's 3.10.11 build;
  3.10.10 on macOS). sampctl projects (`pawn.json`) build through sampctl when it is on PATH.
- **Linux only**: the compiler and the open.mp server are 32-bit. On Debian/Ubuntu:
  `sudo apt install libc6-i386 lib32stdc++6 lib32atomic1`.
- For `run_server` / `/pawn-forge:test`: a local open.mp server directory.

### Options

Set when installing, or later with `/plugin configure pawn-forge@pawn-forge`:

| Option | Default | Purpose |
|---|---|---|
| Python command | `python3` | Interpreter for the MCP server and hooks |
| pawncc path | auto | Explicit compiler path |
| Extra include directories | none | Added to every compile (`:` or `;` separated) |
| Lint Pawn files after each edit | on | The edit-time lint hook |

## Tools

| Tool | Purpose |
|---|---|
| `project_info` | Root, main script, includes, libraries detected, platform (SA-MP vs open.mp), plugins/components, compiler |
| `compile` | Real compiler run on a file or inline snippet: structured diagnostics with fix hints, stack estimate, `-d3` debug info. Normalises backslash `#include` paths on Linux/macOS so YSI builds there. |
| `install_compiler` | Downloads the community compiler into the plugin's data directory |
| `lint` / `lint_rules` | Static analysis (rules below), with inline suppression `// pawnforge-ignore PF101` |
| `analyze_log` | CrashDetect runtime errors and backtraces, server crashes with the suspect plugin, long callbacks, missing natives, plugin load failures; grouped by root cause, with source context |
| `lookup` | Vehicles, weapons, skins, interiors (with coordinates), animations, server limits |
| `api_lookup` | Exact signatures: open.mp, Streamer, MySQL R41, sscanf2, Pawn.CMD, plus the project's own includes |
| `migrate_openmp` | SA-MP to open.mp: includes, renames, deprecations, tagged constants, callback headers, plugin notes; diff, dry run by default, backup on write |
| `convert_textdraws` | Editor export to a guarded module with arrays, named indices and Create/Destroy/Show/Hide |
| `run_server` | Boots open.mp headlessly on a free, unannounced port; reports boot errors, runtime incidents and YSI y_testing results |

## Lint rules

<!-- RULES:START -->
| Rule | Severity | Category | Detects |
|---|---|---|---|
| PF101 | error | buffer | Size argument measures a different buffer |
| PF102 | error | buffer | Size argument larger than the destination buffer |
| PF103 | warning | buffer | Player-name buffer smaller than MAX_PLAYER_NAME |
| PF104 | error | buffer | Format specifiers do not match the arguments |
| PF105 | error | buffer | sscanf string specifier without a size |
| PF106 | warning | buffer | Client message longer than 144 characters |
| PF107 | warning | buffer | Very large local array |
| PF201 | error | security | SQL query built with %s (unescaped) |
| PF202 | warning | security | mysql_format inserts a quoted value with %s instead of %e |
| PF203 | warning | security | Weak password hashing |
| PF301 | warning | database | Legacy (pre-R40) MySQL plugin API |
| PF302 | warning | database | Blocking mysql_query on the server thread |
| PF303 | error | database | Cache from mysql_query is never deleted |
| PF304 | warning | database | SQLite result set not freed |
| PF305 | warning | database | File-based account storage (dini/dfile/dudb/DOF2/y_ini) |
| PF401 | warning | lifecycle | Repeating timer ID discarded |
| PF402 | info | lifecycle | Timer ID stored but never killed |
| PF403 | warning | lifecycle | Global TextDraw created in a repeating callback without TextDrawDestroy |
| PF404 | warning | lifecycle | Player TextDraw created in a repeating callback without PlayerTextDrawDestroy |
| PF405 | info | lifecycle | Entity created in a repeating callback with no matching destroy in the file |
| PF406 | info | performance | Many static CreateObject calls |
| PF501 | warning | modernize | strtok/strcmp command parsing |
| PF502 | info | modernize | dcmd/zcmd-era command processor |
| PF503 | info | modernize | Loop over every player slot |
| PF504 | warning | performance | Expensive work inside OnPlayerUpdate |
| PF505 | info | modernize | Magic number dialog ID |
| PF506 | info | modernize | SA-MP include on an open.mp-capable script |
| PF601 | error | validation | Invalid vehicle model ID |
| PF602 | error | validation | Invalid skin ID |
| PF603 | error | validation | Weapon ID that cannot be given |
| PF604 | error | validation | Unknown animation |
<!-- RULES:END -->

Severity: `error` = crash, memory corruption or exploit; `warning` = leak, blocking work or weak practice;
`info` = modernisation. Suppress with `// pawnforge-ignore PF101` (same line), `// pawnforge-ignore-next-line`
or `// pawnforge-ignore-file PF503`.

## How the pieces fit

```text
 you ──► Claude ──► skills (what good Pawn looks like, step-by-step workflows)
             │
             ├──► MCP tools ──► pawncc / sampctl ──► diagnostics ──► fix ──► recompile
             │              ├─► linter, log analyser, migrator, TextDraw converter
             │              ├─► reference data (generated from upstream, see below)
             │              └─► omp-server (headless tests)
             └──► hooks: lint each edit · detect Pawn projects
```

## Data provenance

Everything in `server/data/` is generated by `tools/build_data.py` from upstream sources; nothing is typed by hand:

- open.mp documentation (`openmultiplayer/web`): vehicles, weapons, skins, interiors, animations, limits
- open.mp standard library (`openmultiplayer/omp-stdlib`): natives, callbacks, `#pragma deprecated` table
- Incognito's Streamer, pBlueG's MySQL R41, Y_Less's sscanf2, katursis's Pawn.CMD: native signatures

`server/data/sources.json` records the exact upstream commits. To refresh, clone those repositories into one
directory and run `python3 tools/build_data.py --sources <dir>`.

## Development

```bash
cd plugins/pawn-forge
python3 -m unittest discover -s tests -v
```

Integration tests (real compiler, real headers, real server) run when these are set, and are skipped otherwise:
`PAWNFORGE_PAWNCC` (compiler), `PAWNFORGE_TEST_INC` (a directory holding `omp-stdlib`, `samp-stdlib`, `pawn-stdlib`,
`YSI-Includes`, `ysiroot`, `samp-streamer-plugin`, `mysqlinc`, `sscanf`, `Pawn.CMD`), `PAWNFORGE_TEST_SERVER`
(an open.mp server directory).

## Limitations

- The linter is pattern-based, not a full Pawn parser. It is tuned to stay quiet when unsure (unresolved array
  sizes, macro-generated code), so it misses some defects rather than flooding you with false ones.
- Runtime errors are only visible with CrashDetect loaded and code compiled with `-d3`.
- `run_server` needs a local open.mp server; the SA-MP server has no command-line script override.
- The macOS compiler build is x86_64 (runs under Rosetta 2 on Apple Silicon).

## License

MIT. Generated reference data remains under the licences of the upstream projects it was extracted from.
