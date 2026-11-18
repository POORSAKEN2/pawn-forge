# Pawn Forge

**Agent skills, standalone CLI, and MCP plugin for Claude Code, Google Antigravity, Cursor, Codex, and 20+ coding agents that turn your AI assistant into a SA-MP 0.3.7 / open.mp engineer instead of a code guesser.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)
![Platforms](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)
![open.mp](https://img.shields.io/badge/open.mp-ready-orange)
![SA-MP 0.3.7](https://img.shields.io/badge/SA--MP-0.3.7-yellow)
![Agents: Agensi | Claude Code | Antigravity](https://img.shields.io/badge/Agents-Agensi%20%7C%20Claude%20Code%20%7C%20Antigravity-purple)

General-purpose AI models write Pawn the way 2008-2014 forum tutorials did: `strtok` command parsers, `dini`
account files, `format(query, ..., "'%s'")` SQL, `new string[256]` everywhere, and vehicle IDs or animation names
pulled from thin air. That code compiles (sometimes), then crashes servers and leaks accounts.

Pawn Forge puts deterministic tools in the loop. Your AI assistant **compiles** what it writes
with the real Pawn compiler, **lints** it for the defects that actually crash or compromise servers, **looks up** IDs
and function signatures from official open.mp data, SA-MP 0.3.7 stdlib, and real library headers, and can **run tests** on a headless open.mp server.

---

## Contents

- [Features](#features)
- [Quick start](#quick-start)
  - [Agensi & Multi-Agent Quick Start (Recommended)](#agensi--multi-agent-quick-start-recommended)
  - [In Claude Code (Plugin)](#in-claude-code-plugin)
  - [In Google Antigravity (Plugin)](#in-google-antigravity-plugin)
- [Requirements](#requirements)
- [Configuration](#configuration)
- [Using it](#using-it)
  - [Skills & Workflows](#skills--workflows)
  - [Standalone CLI Subcommands](#standalone-cli-subcommands)
  - [Natural Conversation](#natural-conversation)
  - [Agents & Hooks](#agents--hooks)
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
  projects) and returns structured diagnostics with fix hints and stack-usage estimates. Supports `compat: true` (`-Z`)
  for legacy SA-MP 0.3.7 includes, and normalises YSI's backslash include paths automatically so YSI builds on Linux and macOS too.
- **Static analysis built for Pawn.** 37 rules for buffer/`sizeof` mismatches, format-specifier vs argument
  mismatches, unsized `sscanf` strings, SQL injection, weak password hashing, unfreed MySQL caches and SQLite
  results, leaked timers/TextDraws/BitStreams, blocking queries, heavy `OnPlayerUpdate` work (`IsPlayerInRangeOfPoint`),
  delayed `Kick`/`Ban`, unguarded `strcmp`, combat bounds, RCON `%s` injection, legacy libraries, and invalid
  vehicle/skin/weapon/animation IDs.
- **Crash triage.** Parses `server_log.txt` / `log.txt` and CrashDetect output, groups thousands of repeated errors
  into root causes, shows the source lines around each backtrace frame, identifies the plugin behind a crash, and
  lists missing natives.
- **No invented IDs or signatures.** 212 vehicles, 53 weapons, 311 skins, 129 interiors with coordinates, 1,812
  animations, and 2,022 API declarations (1,836 natives + 186 callbacks) from open.mp, SA-MP 0.3.7 (`samp-stdlib`),
  Streamer, MySQL R41, sscanf2, Pawn.CMD, Pawn.RakNet, samp-bcrypt, and ColAndreas — all generated from upstream sources.
- **SA-MP to open.mp migration.** Includes, renamed and deprecated natives, tagged constants (`true`, `WEAPON_*`,
  `TEXT_DRAW_FONT_*`), callback headers like `WEAPON:reason`, plugin-to-component notes. Dry run with a diff by
  default; a backup is kept when editing in place.
- **TextDraw scaffolding.** Converts raw TextDraw editor exports into a clean module with arrays, named indices and
  guarded Create/Destroy/Show/Hide functions, and flags off-canvas or mis-configured TextDraws.
- **Headless testing.** Boots a local open.mp server on a free, unannounced port and reports boot errors, runtime
  incidents and YSI y_testing results down to the failing assertion.
- **11 portable Agent Skills.** Covers baseline modern Pawn (`pawn-standards`), roleplay systems (`pawn-roleplay`),
  server-authoritative anti-cheat (`pawn-anticheat`), SA-MP/open.mp plugin ecosystems (`pawn-ecosystem`), auditing,
  building, crash debugging, open.mp migration, DB modernization, TextDraw scaffolding, and headless testing.

## Quick start

### Agensi & Multi-Agent Quick Start (Recommended)

Install the 11 canonical Agent Skills across **Claude Code, Cursor, GitHub Copilot, Windsurf, OpenAI Codex, Google Antigravity**, and 20+ other agents via [Agensi](https://agensi.io) / `skills`:

```bash
npx skills add POORSAKEN2/pawn-forge
```

Install the zero-dependency Python CLI so any skill can compile, lint, look up IDs/APIs, and run headless tests from your shell:

```bash
pip install git+https://github.com/POORSAKEN2/pawn-forge.git
```

Verify the installation in any Pawn server directory:

```bash
pawnforge info .
pawnforge lint gamemodes/main.pwn --strict
pawnforge compile gamemodes/main.pwn
```

*(You can also run `pawnforge-mcp` to expose the same 11 tools over stdio MCP, or let the skill-bundled `scripts/pawnforge_exec.py` auto-locate the CLI.)*

---

### In Claude Code (Plugin)

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

---

### In Google Antigravity (Plugin)

Pawn Forge can be used in Antigravity either via the universal `npx skills add` flow above, or as an Antigravity plugin from `./plugins/pawn-forge`.

> **Note:** Copy or point `.agents/plugins/pawn-forge` to the `plugins/pawn-forge` subdirectory (not the repository root), so Antigravity does not load both `skills/` and `plugins/pawn-forge/skills/` simultaneously.

#### Option A: Workspace / Project Plugin

```bash
# From your Pawn project root:
git clone --depth 1 https://github.com/POORSAKEN2/pawn-forge.git /tmp/pawn-forge-repo
mkdir -p .agents/plugins
cp -r /tmp/pawn-forge-repo/plugins/pawn-forge .agents/plugins/pawn-forge
rm -rf /tmp/pawn-forge-repo
```

Antigravity automatically discovers `.agents/plugins/pawn-forge`, activates its Pawn skills (`pawn-standards`, `build`, `audit`, `roleplay`, `anticheat`, `ecosystem`, etc.), launches the MCP server, and enables the lifecycle hooks.

#### Option B: Global Plugin (All Projects)

Clone the repository and copy `./plugins/pawn-forge` to your global Antigravity plugins directory:

- **Windows (PowerShell)**:
  ```powershell
  git clone --depth 1 https://github.com/POORSAKEN2/pawn-forge.git "$env:TEMP\pawn-forge-repo"
  Copy-Item -Recurse "$env:TEMP\pawn-forge-repo\plugins\pawn-forge" "$env:USERPROFILE\.gemini\config\plugins\pawn-forge"
  Remove-Item -Recurse -Force "$env:TEMP\pawn-forge-repo"
  ```
- **Linux / macOS**:
  ```bash
  git clone --depth 1 https://github.com/POORSAKEN2/pawn-forge.git /tmp/pawn-forge-repo
  mkdir -p ~/.gemini/config/plugins
  cp -r /tmp/pawn-forge-repo/plugins/pawn-forge ~/.gemini/config/plugins/pawn-forge
  rm -rf /tmp/pawn-forge-repo
  ```

#### Option C: Standalone MCP Server

If you only want the MCP tools in Antigravity or another MCP client without the full plugin wrapper, add the server to `~/.gemini/config/mcp_config.json` or your project's `.agents/mcp_config.json`:

```json
{
  "mcpServers": {
    "pawn-forge": {
      "command": "python",
      "args": [
        "<path-to-pawn-forge>/plugins/pawn-forge/server/pawn_mcp.py"
      ],
      "env": {
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1"
      }
    }
  }
}
```

## Requirements

| Requirement | Notes |
|---|---|
| **Coding Agent / IDE** | Any Agensi-compatible agent (`npx skills add`), Claude Code, or Google Antigravity |
| **Python 3.8+** | On PATH. Standard library only; nothing extra to install beyond `pawnforge` (optional for plugin mode). On Windows set the *Python command* option to `py` or `python`. |
| **Pawn compiler** | pawncc 3.10.x. Found automatically in the project's `qawno/` or `pawno/`, on PATH, or via the *pawncc path* option. `install_compiler` / `pawnforge install-compiler` can download the community build for you (open.mp's 3.10.11; 3.10.10 on macOS). |
| **32-bit runtime (Linux only)** | The compiler and open.mp server are 32-bit. Debian/Ubuntu: `sudo apt install libc6-i386 lib32stdc++6 lib32atomic1` |
| **open.mp server** (optional) | Only for headless tests (`/pawn-forge:test`, `run_server`, `pawnforge run-server`) |

## Configuration

In Claude Code, you are asked for these on install; change them any time with `/plugin configure pawn-forge@pawn-forge`. In Antigravity or standalone CLI setups, set them via environment variables.

| Option | Default | Environment Variable | Purpose |
|---|---|---|---|
| Python command | `python3` / `py` | `PYTHON` | Interpreter for the MCP server and hooks (`py` or `python` on Windows) |
| pawncc path | auto-detect | `PAWNFORGE_PAWNCC` | Explicit path to `pawncc` / `pawncc.exe` |
| Extra include directories | none | `PAWNFORGE_INCLUDE_PATHS` | Added to every compile, separated by `:` (macOS/Linux) or `;` (Windows) |
| Lint Pawn files after each edit | on | — | Feeds lint findings on the lines changed back to the assistant |

Project include folders (`include/`, `qawno/include`, `pawno/include`, sampctl `dependencies/`) are found
automatically.

## Using it

### Skills & Workflows

All 11 skills live under `skills/` (Agensi / multi-agent format) and are mirrored into `plugins/pawn-forge/skills/` for Claude Code slash commands and Antigravity plugin loading:

| Agensi Skill | Claude Code Command | What it does |
|---|---|---|
| `pawn-standards` | *(auto-loaded)* | Modern Pawn safety, SA-MP 0.3.7 & open.mp idioms, strings, SQL, YSI, Streamer, Pawn.CMD |
| `pawn-build` | `/pawn-forge:build [file]` | Compile and fix every error and warning until the build is clean |
| `pawn-audit` | `/pawn-forge:audit [path]` | Security, anti-cheat, stability and modernisation audit with a prioritised, verified report |
| `pawn-migrate-openmp` | `/pawn-forge:migrate-openmp [file]` | Port a SA-MP script to open.mp and compile it clean |
| `pawn-debug-crash` | `/pawn-forge:debug-crash [log]` | Trace runtime errors and crashes to the source line and fix them |
| `pawn-textdraw` | `/pawn-forge:textdraw [export] [Prefix]` | Turn a TextDraw editor export into a clean module |
| `pawn-modernize-storage` | `/pawn-forge:modernize-storage [sqlite\|mysql]` | Replace dini / y_ini storage with a database, including data migration and bcrypt re-hashing |
| `pawn-test` | `/pawn-forge:test [server-dir]` | Write and run YSI y_testing tests on a headless open.mp server |
| `pawn-roleplay` | `/pawn-forge:roleplay [system]` | Roleplay server architecture: multi-character accounts, bcrypt, atomic inventory, vehicles/properties, factions, overflow-safe economy, 144-char chat |
| `pawn-anticheat` | `/pawn-forge:anticheat [system]` | Server-authoritative anti-cheat: shadow cash/weapons/HP, vehicle-entry exceptions, `GetTickCount()` grace windows, combat/dialog/RCON guards, RakNet/Nex-AC |
| `pawn-ecosystem` | `/pawn-forge:ecosystem [library]` | Deep library patterns for `Pawn.RakNet`, YSI 5 (`y_inline`/`y_dialog`/`y_va`/`y_bits`), Streamer, ColAndreas/MapAndreas, `samp-bcrypt`, `Pawn.CMD`, `sscanf2` |

### Standalone CLI Subcommands

`pawnforge` maps all 11 MCP tools 1:1 to CLI subcommands (pass `--json` for machine output or `--strict` to exit `1` on compile/lint errors):

| CLI Subcommand | MCP Tool | Purpose |
|---|---|---|
| `pawnforge info [dir]` | `project_info` | Project root, main script, includes, libraries, platform (`sa-mp` or `open.mp`), compiler |
| `pawnforge compile [file\|--code -]` | `compile` | Compile a `.pwn` file or stdin snippet (`--compat` for `-Z`, `--output alongside`) |
| `pawnforge install-compiler` | `install_compiler` | Download the community open.mp compiler into the local data folder |
| `pawnforge lint [path\|--code -]` | `lint` | Static analysis across 37 rules (`--rules`, `--exclude`, `--min-severity`, `--strict`) |
| `pawnforge lint-rules` | `lint_rules` | List all 37 lint rules with severity and category |
| `pawnforge analyze-log [path\|--text -]` | `analyze_log` | CrashDetect and server log root-cause analysis with source context |
| `pawnforge lookup <kind> [query]` | `lookup` | Verified `vehicle`, `weapon`, `skin`, `interior`, `animation`, and `limit` entries |
| `pawnforge api [--name\|--query]` | `api_lookup` | Exact signatures with `--platform auto\|open.mp\|sa-mp`, `--library`, and `--project-dir` |
| `pawnforge migrate [file\|--code -]` | `migrate_openmp` | SA-MP 0.3.7 to open.mp migration plan or rewrite (`--write none\|copy\|in_place`) |
| `pawnforge textdraw [file\|--code -]` | `convert_textdraws` | Convert TextDraw editor export to a guarded module (`--target openmp\|samp`) |
| `pawnforge run-server <dir>` | `run_server` | Headless open.mp boot smoke test or `y_testing` runner |

### Natural Conversation

You don't need the slash commands. With the skills or plugin installed, ordinary requests use the tools automatically:

- *"Add a /givecash admin command with Pawn.CMD and sscanf."*
- *"Why does my server crash? Here's log.txt."*
- *"What's the vehicle ID for the NRG-500, and give me a sitting animation."*
- *"Harden our OnPlayerWeaponShot and OnIncomingPacket against fake-bullet exploits."*
- *"Build an atomic character inventory and property system in MySQL R41."*
- *"Compile gamemodes/main.pwn and fix any build errors."*

### Agents & Hooks

- **`pawn-auditor`**: a read-only auditor for large codebases that verifies `PF101`–`PF802` findings and returns a compact, prioritised report.
- **`pawn-build-fixer`**: takes a broken SA-MP 0.3.7 or open.mp build to clean without filling your conversation with compiler output.
- **Edit-time lint hook**: after editing a `.pwn`/`.inc` file, changed lines are linted and any issues are fed back without repeating pre-existing noise.
- **Session-start hook**: detects Pawn projects and announces available tools and workflows (silent outside Pawn projects).

## Tools

The plugin's MCP server (`pawnforge-mcp` / `plugins/pawn-forge/server/pawn_mcp.py`) exposes the same 11 tools:

| Tool | Purpose |
|---|---|
| `project_info` | Project root, main script, includes, detected libraries, platform (SA-MP or open.mp), plugins/components, available compiler |
| `compile` | Real compiler run on a file or snippet with structured diagnostics and fix hints |
| `install_compiler` | Download the community compiler into the plugin's data folder |
| `lint` / `lint_rules` | Static analysis (37 rules) and the rule catalogue |
| `analyze_log` | CrashDetect and server-log analysis, grouped by root cause, with source context |
| `lookup` | Vehicles, weapons, skins, interiors, animations and server limits |
| `api_lookup` | Exact signatures from open.mp, SA-MP 0.3.7 (`samp-stdlib`), Streamer, MySQL R41, sscanf2, Pawn.CMD, Pawn.RakNet, samp-bcrypt, ColAndreas, and your project's own includes (`platform="auto"\|"open.mp"\|"sa-mp"`) |
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
| PF701 | warning | Immediate `Kick`/`Ban` after message or dialog |
| PF702 | error | Unguarded `strcmp` on `inputtext` (empty string matches password) |
| PF703 | warning | Unguarded array index in combat callback (`weaponid`/`damagedid`/`issuerid`/`hitid`) |
| PF704 | error | `SendRconCommand` built with `%s` |
| PF801 | warning | `Pawn.RakNet` `BitStream` not freed with `BS_Delete` |
| PF802 | info | `IsPlayerInRangeOfPoint` inside `OnPlayerUpdate` |

Suppress a finding deliberately with a comment: `// pawnforge-ignore PF101` (same line),
`// pawnforge-ignore-next-line`, or `// pawnforge-ignore-file PF503`.

## How it works

```text
 you ──► Agent (Claude / Antigravity / Cursor / Codex) ──► skills: modern Pawn + 10 workflows
             │
             ├──► MCP server or `pawnforge` CLI ──► pawncc / sampctl ──► diagnostics ──► fix ──► recompile
             │                                  ├─► linter (37 rules) · log analyser · migrator · TextDraw converter
             │                                  ├─► reference data generated from upstream sources
             │                                  └─► omp-server (headless tests)
             └──► hooks (plugin mode): lint each Pawn edit · detect Pawn projects
```

## Data provenance

Nothing in `plugins/pawn-forge/server/data/` is typed by hand. `tools/build_data.py` generates it from:

- **open.mp documentation** (`openmultiplayer/web`): vehicles, weapons, skins, interiors, animations and limits
- **open.mp standard library** (`openmultiplayer/omp-stdlib`): native and callback signatures and the
  `#pragma deprecated` migration table
- **SA-MP 0.3.7 standard library** (`samp-stdlib`): native and callback signatures for `platform="sa-mp"`
- **Incognito's Streamer**, **pBlueG's MySQL R41**, **Y_Less's sscanf2**, **katursis's Pawn.CMD**, **katursis's Pawn.RakNet**, **Sreyas-Sreelal's samp-bcrypt**, **Pottus's ColAndreas**: native and callback signatures

`server/data/sources.json` records the exact upstream commits used.

## Repository layout

```text
pyproject.toml                      PEP 621 package (`pawnforge` + `pawnforge-mcp`)
skills/                             11 canonical Agensi skills (`pawn-*`, references/, scripts/)
.claude-plugin/marketplace.json     marketplace definition
plugins/pawn-forge/
  .claude-plugin/plugin.json        plugin manifest, options and MCP server
  server/                           MCP server (pawn_mcp.py), CLI (pawnforge/cli.py) and core modules
    data/                           generated reference data
  skills/                           plugin-synced skills (generated by tools/sync_skills.py)
  agents/                           pawn-auditor, pawn-build-fixer
  hooks/hooks.json, scripts/        lint-on-edit and session-start hooks
  tools/build_data.py               regenerates server/data from upstream
  tools/sync_skills.py              syncs skills/ -> plugins/pawn-forge/skills/ (--check in CI/tests)
  tools/pawnforge_exec.py           zero-dependency CLI bootstrapper synced into skills
  tests/                            unit and integration tests, fixtures
```

## Development

```bash
python -m unittest discover -s plugins/pawn-forge/tests -t plugins/pawn-forge/tests -v
python plugins/pawn-forge/tools/sync_skills.py --check
```

Unit tests need nothing but Python. Integration tests run against the real compiler, real headers and a real
server when these environment variables are set, and are skipped otherwise:

| Variable | Points to |
|---|---|
| `PAWNFORGE_PAWNCC` | a pawncc binary |
| `PAWNFORGE_TEST_INC` | a folder containing `omp-stdlib`, `samp-stdlib`, `pawn-stdlib`, `YSI-Includes`, `ysiroot`, `samp-streamer-plugin`, `mysqlinc`, `sscanf`, `Pawn.CMD` |
| `PAWNFORGE_TEST_SERVER` | an open.mp server folder |

Validate the manifests with `claude plugin validate ./plugins/pawn-forge` and `claude plugin validate .`.
When editing any skill under `skills/`, run `python plugins/pawn-forge/tools/sync_skills.py` to keep `plugins/pawn-forge/skills/` synchronized (`test_skills.py` enforces `sync_skills.py --check`).

To refresh the reference data, clone the upstream repositories listed above into one folder and run
`python3 plugins/pawn-forge/tools/build_data.py --sources <folder>`.

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
