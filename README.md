# Pawn Forge

**A Claude Code plugin that turns Claude into a SA-MP / open.mp engineer instead of a code guesser.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)
![Platforms](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)
![open.mp](https://img.shields.io/badge/open.mp-ready-orange)

General-purpose AI models write Pawn the way 2008-2014 forum tutorials did: `strtok` command parsers, `dini`
account files, `format(query, ..., "'%s'")` SQL, `new string[256]` everywhere, and vehicle IDs or animation names
pulled from thin air. That code compiles (sometimes), then crashes servers and leaks accounts.

Pawn Forge puts deterministic tools in the loop. Claude **compiles** what it writes with the real Pawn compiler,
**lints** it for the defects that actually crash or compromise servers, **looks up** IDs and function signatures
from official open.mp data and real library headers, and can **run tests** on a headless open.mp server.

---

## Contents

- [Features](#features)
- [Quick start](#quick-start)
- [Requirements](#requirements)
- [Configuration](#configuration)
- [Using it](#using-it)
- [Tools](#tools)
- [Lint rules](#lint-rules)
- [How it works](#how-it-works)
- [Data provenance](#data-provenance)
- [Repository layout](#repository-layout)
- [Development](#development)
- [Limitations](#limitations)
- [License](#license)

## Features

- **Real compiler in the loop.** Compiles files or snippets with pawncc 3.10.x (or sampctl for `pawn.json`
  projects) and returns structured diagnostics with fix hints and stack-usage estimates. Claude iterates until the
  build is clean. YSI's backslash include paths are normalised automatically so YSI builds on Linux and macOS too.
- **Static analysis built for Pawn.** 31 rules for buffer/`sizeof` mismatches, format-specifier vs argument
  mismatches, unsized `sscanf` strings, SQL injection, weak password hashing, unfreed MySQL caches and SQLite
  results, leaked timers and TextDraws, blocking queries, heavy `OnPlayerUpdate` work, legacy libraries, and invalid
  vehicle/skin/weapon/animation IDs.
- **Crash triage.** Parses `server_log.txt` / `log.txt` and CrashDetect output, groups thousands of repeated errors
  into root causes, shows the source lines around each backtrace frame, identifies the plugin behind a crash, and
  lists missing natives.
- **No invented IDs or signatures.** 212 vehicles, 53 weapons, 311 skins, 129 interiors with coordinates, 1,812
  animations, and 1,339 native signatures from open.mp, Streamer, MySQL R41, sscanf2 and Pawn.CMD, all generated
  from upstream sources.
- **SA-MP to open.mp migration.** Includes, renamed and deprecated natives, tagged constants (`true`, `WEAPON_*`,
  `TEXT_DRAW_FONT_*`), callback headers like `WEAPON:reason`, plugin-to-component notes. Dry run with a diff by
  default; a backup is kept when editing in place.
- **TextDraw scaffolding.** Converts raw TextDraw editor exports into a clean module with arrays, named indices and
  guarded Create/Destroy/Show/Hide functions, and flags off-canvas or mis-configured TextDraws.
- **Headless testing.** Boots a local open.mp server on a free, unannounced port and reports boot errors, runtime
  incidents and YSI y_testing results down to the failing assertion.
- **Modern-practice knowledge.** A skill that loads automatically for `.pwn`/`.inc` work, covering strings and
  buffers, MySQL R41, SQLite, YSI 5, Streamer, Pawn.CMD, sscanf and open.mp. Every code sample in it is compiled in
  the test suite.

## Quick start

In Claude Code:

```text
/plugin marketplace add POORSAKEN2/pawn-forge
/plugin install pawn-forge@pawn-forge
```

Or from a terminal:

```bash
claude plugin marketplace add POORSAKEN2/pawn-forge
claude plugin install pawn-forge@pawn-forge
```

Then open your server or gamemode folder in Claude Code and ask, for example:

```text
/pawn-forge:build gamemodes/main.pwn
```

To try it without installing, clone this repo and run `claude --plugin-dir ./plugins/pawn-forge`.

## Requirements

| Requirement | Notes |
|---|---|
| **Claude Code** | Recent version with plugin support |
| **Python 3.8+** | On PATH. Standard library only; nothing to `pip install`. On Windows set the *Python command* option to `py` or `python`. |
| **Pawn compiler** | pawncc 3.10.x. Found automatically in the project's `qawno/` or `pawno/`, on PATH, or via the *pawncc path* option. The `install_compiler` tool can download the community build for you (open.mp's 3.10.11; 3.10.10 on macOS). |
| **32-bit runtime (Linux only)** | The compiler and open.mp server are 32-bit. Debian/Ubuntu: `sudo apt install libc6-i386 lib32stdc++6 lib32atomic1` |
| **open.mp server** (optional) | Only for headless tests (`/pawn-forge:test`, `run_server`) |

## Configuration

You are asked for these on install; change them any time with `/plugin configure pawn-forge@pawn-forge`.

| Option | Default | Purpose |
|---|---|---|
| Python command | `python3` | Interpreter for the MCP server and hooks (`py` on Windows) |
| pawncc path | auto-detect | Explicit path to `pawncc` / `pawncc.exe` |
| Extra include directories | none | Added to every compile, separated by `:` (macOS/Linux) or `;` (Windows) |
| Lint Pawn files after each edit | on | Feeds lint findings on the lines Claude just changed back to Claude |

Project include folders (`include/`, `qawno/include`, `pawno/include`, sampctl `dependencies/`) are found
automatically.

## Using it

### Workflows

| Command | What it does |
|---|---|
| `/pawn-forge:build [file]` | Compile and fix every error and warning until the build is clean |
| `/pawn-forge:audit [path]` | Security, stability and modernisation audit with a prioritised, verified report |
| `/pawn-forge:migrate-openmp [file]` | Port a SA-MP script to open.mp and compile it clean |
| `/pawn-forge:debug-crash [log]` | Trace runtime errors and crashes to the source line and fix them |
| `/pawn-forge:textdraw [export] [Prefix]` | Turn a TextDraw editor export into a clean module |
| `/pawn-forge:modernize-storage [sqlite\|mysql]` | Replace dini / y_ini storage with a database, including data migration and password re-hashing |
| `/pawn-forge:test [server-dir]` | Write and run YSI y_testing tests on a headless open.mp server |

### Just ask

You don't need the commands. With the plugin installed, ordinary requests use the tools automatically:

- "Add a /givecash admin command with Pawn.CMD and sscanf."
- "Why does my server crash? Here's log.txt."
- "What's the vehicle ID for the NRG-500, and give me a sitting animation."
- "Is this login system safe?"
- "Move our accounts from dini to SQLite."

### Agents

- **pawn-auditor**: a read-only auditor for large codebases that returns a compact, prioritised report.
- **pawn-build-fixer**: takes a broken build to clean without filling your conversation with compiler output.

### Hooks

- After Claude edits a `.pwn`/`.inc` file, the changed lines are linted and any issues are fed back to Claude.
  Pre-existing problems elsewhere in the file are not repeated on every edit.
- When a session starts in a Pawn project, Claude is reminded which tools exist. Outside Pawn projects it stays silent.

## Tools

The plugin's MCP server exposes:

| Tool | Purpose |
|---|---|
| `project_info` | Project root, main script, includes, detected libraries, platform (SA-MP or open.mp), plugins/components, available compiler |
| `compile` | Real compiler run on a file or snippet with structured diagnostics and fix hints |
| `install_compiler` | Download the community compiler into the plugin's data folder |
| `lint` / `lint_rules` | Static analysis and the rule catalogue |
| `analyze_log` | CrashDetect and server-log analysis, grouped by root cause, with source context |
| `lookup` | Vehicles, weapons, skins, interiors, animations and server limits |
| `api_lookup` | Exact signatures from open.mp, Streamer, MySQL R41, sscanf2, Pawn.CMD and your project's own includes |
| `migrate_openmp` | SA-MP to open.mp migration plan or rewrite, as a diff |
| `convert_textdraws` | TextDraw editor export to a guarded module |
| `run_server` | Headless open.mp boot and y_testing run |

## Lint rules

| Rule | Severity | Detects |
|---|---|---|
| PF101 | error | Size argument measures a different buffer (`format(a, sizeof b, ...)`) |
| PF102 | error | Size argument larger than the destination buffer |
| PF103 | warning | Player-name buffer smaller than `MAX_PLAYER_NAME` |
| PF104 | error | Format specifiers do not match the arguments (`format`, `SetTimerEx`, `mysql_tquery`...) |
| PF105 | error | `sscanf` string specifier without a size |
| PF106 | warning | Client message longer than 144 characters |
| PF107 | warning | Very large local array on the stack |
| PF201 | error | SQL built with unescaped `%s` |
| PF202 | warning | `mysql_format` quoted value with `%s` instead of `%e` |
| PF203 | warning | Weak password hashing (udb_hash, Whirlpool, MD5, SHA256_PassHash) |
| PF301 | warning | Legacy pre-R40 MySQL API |
| PF302 | warning | Blocking `mysql_query` |
| PF303 | error | `mysql_query` cache never deleted |
| PF304 | warning | SQLite result not freed |
| PF305 | warning | File-based storage (dini, dfile, dudb, DOF2, y_ini) |
| PF401 | warning | Repeating timer ID thrown away in a per-player context |
| PF402 | info | Timer ID stored but never killed |
| PF403 | warning | Global TextDraw created repeatedly without being destroyed |
| PF404 | warning | Player TextDraw created repeatedly without being destroyed |
| PF405 | info | Entity created repeatedly with no matching destroy |
| PF406 | info | Many static `CreateObject` calls (use Streamer) |
| PF501 | warning | `strtok` / `strcmp` command parsing |
| PF502 | info | dcmd / zcmd-era command processor |
| PF503 | info | Loop over every player slot (use `foreach`) |
| PF504 | warning | Expensive work inside `OnPlayerUpdate` |
| PF505 | info | Magic-number dialog ID |
| PF506 | info | `#include <a_samp>` where open.mp is available |
| PF601 | error | Invalid vehicle model ID |
| PF602 | error | Invalid skin ID |
| PF603 | error | Weapon ID that cannot be given |
| PF604 | error | Unknown animation library or name |

Suppress a finding deliberately with a comment: `// pawnforge-ignore PF101` (same line),
`// pawnforge-ignore-next-line`, or `// pawnforge-ignore-file PF503`.

## How it works

```text
 you ──► Claude ──► skills: what good Pawn looks like + step-by-step workflows
             │
             ├──► MCP tools ──► pawncc / sampctl ──► diagnostics ──► fix ──► recompile
             │              ├─► linter · log analyser · migrator · TextDraw converter
             │              ├─► reference data generated from upstream sources
             │              └─► omp-server (headless tests)
             │
             └──► hooks: lint each Pawn edit · detect Pawn projects
```

## Data provenance

Nothing in `plugins/pawn-forge/server/data/` is typed by hand. `tools/build_data.py` generates it from:

- **open.mp documentation** (`openmultiplayer/web`): vehicles, weapons, skins, interiors, animations and limits
- **open.mp standard library** (`openmultiplayer/omp-stdlib`): native and callback signatures and the
  `#pragma deprecated` migration table
- **Incognito's Streamer**, **pBlueG's MySQL R41**, **Y_Less's sscanf2**, **katursis's Pawn.CMD**: native signatures

`server/data/sources.json` records the exact upstream commits used.

## Repository layout

```text
.claude-plugin/marketplace.json     marketplace definition
plugins/pawn-forge/
  .claude-plugin/plugin.json        plugin manifest, options and MCP server
  server/                           MCP server (pawn_mcp.py) and the pawnforge package
    data/                           generated reference data
  skills/                           pawn-standards + 7 workflow skills
  agents/                           pawn-auditor, pawn-build-fixer
  hooks/hooks.json, scripts/        lint-on-edit and session-start hooks
  tools/build_data.py               regenerates server/data from upstream
  tests/                            unit and integration tests, fixtures
```

## Development

```bash
cd plugins/pawn-forge
python3 -m unittest discover -s tests -v
```

Unit tests need nothing but Python. Integration tests run against the real compiler, real headers and a real
server when these environment variables are set, and are skipped otherwise:

| Variable | Points to |
|---|---|
| `PAWNFORGE_PAWNCC` | a pawncc binary |
| `PAWNFORGE_TEST_INC` | a folder containing `omp-stdlib`, `samp-stdlib`, `pawn-stdlib`, `YSI-Includes`, `ysiroot`, `samp-streamer-plugin`, `mysqlinc`, `sscanf`, `Pawn.CMD` |
| `PAWNFORGE_TEST_SERVER` | an open.mp server folder |

Validate the manifests with `claude plugin validate ./plugins/pawn-forge` and `claude plugin validate .`.

To refresh the reference data, clone the upstream repositories listed above into one folder and run
`python3 tools/build_data.py --sources <folder>`.

Contributions are welcome: open an issue or pull request. New lint rules should come with a fixture line in
`tests/fixtures/legacy_bad.pwn` and a check that they stay quiet on clean code.

## Limitations

- The linter is pattern-based, not a full Pawn parser. It stays quiet when it cannot be sure (unresolved array
  sizes, macro-generated code), so it misses some defects rather than flooding you with false alarms.
- Runtime errors only show up in logs when CrashDetect is loaded and scripts are compiled with `-d3` (the
  `compile` tool always uses `-d3`).
- `run_server` needs a local open.mp server; the SA-MP server has no command-line way to choose a script.
- The macOS compiler build is x86_64 and runs under Rosetta 2 on Apple Silicon.

## License

[MIT](LICENSE). The generated reference data remains under the licences of the upstream projects it was
extracted from.
