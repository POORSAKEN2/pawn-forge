# Design: Pawn Forge Multi-Agent Skills (Agensi) & SA-MP Expansion

**Date:** 2026-11-18
**Status:** Ready for Approval
**Target Repo:** `POORSAKEN2/pawn-forge`

---

## 1. Intent and Why

**Intent:** Transform Pawn Forge from a Claude Code / Google Antigravity plugin into a portable, Agensi-ready suite of AI agent skills compatible with 20+ coding agents (Claude Code, Cursor, GitHub Copilot, Windsurf, Antigravity, Codex, Cline, etc.), backed by a zero-dependency standalone Python CLI fallback, while deeply expanding SA-MP game scripting guidance and static checks across **roleplay systems**, **anti-cheat & server security**, and **specific SA-MP include ecosystems**.

**Why:**
1. **Cross-agent reach:** Most SA-MP and open.mp scripters use Cursor, VS Code + Copilot, Windsurf, or terminal agents rather than only Claude Code. Packaging the project under the open Agent Skills specification (`SKILL.md` + `references/` + `scripts/`) allows one-command installation via Agensi and `npx skills add`.
2. **Real-world SA-MP pain points:** Existing skills cover core syntax, database migration, and TextDraws, but SA-MP servers fail most severely on roleplay system architecture (duplication bugs, async race conditions, persistence leaks), anti-cheat / server-side authority (weapon/money/teleport hacks, dialog spoofing, RakNet crashers), and complex third-party include ecosystems (`Pawn.RakNet`, `YSI 5`, `Streamer`, `ColAndreas`, `samp-bcrypt`).
3. **Deterministic tooling everywhere:** Many agents on Agensi do not run custom MCP servers out of the box, or users install skills without configuring MCP. Exposing every verification tool (`compile`, `lint`, `lookup`, `api_lookup`, `analyze_log`, etc.) through a standalone Python CLI keeps deterministic verification intact across every agent with shell access.

---

## 2. Goals, Non-Goals, and Anti-Goals

### Goals
- **Agensi & Multi-Agent Compatibility:** Provide valid `SKILL.md` directories in a standard root `skills/` hierarchy discoverable by Agensi, `npx skills`, Claude Code, Cursor, GitHub Copilot, Windsurf, and Antigravity, while keeping existing `.claude-plugin/` and `plugins/pawn-forge/` installations working.
- **Standalone Zero-Dependency CLI (`pawnforge`):** Expose all 11 existing MCP tools through a stdlib-only Python CLI and standard `pyproject.toml` package entry point so any terminal-capable agent can run deterministic checks without MCP setup.
- **First-Class SA-MP 0.3.7 & open.mp Support:** Support SA-MP 0.3.7 (`<a_samp>`) ecosystems directly without forcing open.mp migration when maintaining legacy servers, while preserving open.mp as the recommended default for new projects.
- **Roleplay Systems Skill (`pawn-roleplay`):** Authoritative patterns and reference modules for character/account lifecycles, slot/stackable inventories, dynamic vehicles, houses/businesses, factions/jobs, integer-safe economies, and proximity/RP chat.
- **Anti-Cheat & Security Skill (`pawn-anticheat`):** Server-side authoritative models for cash, weapons/ammo, health/armour, movement/airbreak/speed detection, combat validation, dialog/state anti-spoofing, Pawn.RakNet packet/RPC filtering, and Nex-AC integration.
- **Include Ecosystems Skill (`pawn-ecosystem`) & Tooling Expansion:** Deep references and verified signatures for `Pawn.RakNet`, `YSI 5`, `Streamer`, `ColAndreas`/`MapAndreas`, `samp-bcrypt`, `Pawn.CMD`, and `sscanf2`, plus expanded project detection, reference data, and conservative lint rules.
- **Automated Verification:** Validate skill manifests, sync integrity, CLI/MCP parity, lint rules, and compilable Pawn reference snippets via `unittest`.

### Non-Goals
- Shipping pre-compiled OS binaries (`pawncc`, `omp-server`) inside Git or Agensi skill packages; existing auto-detection and opt-in `install_compiler` remain.
- Building a drop-in, black-box anti-cheat filterscript `.amx` (the goal is enabling AI agents to engineer, audit, and integrate anti-cheat directly into user gamemodes).
- Supporting non-Pawn SA-MP frameworks (SampSharp, omp-node, Rust plugins).
- Removing or breaking the existing Claude Code marketplace manifest or Antigravity plugin layout.

### Anti-Goals
- **Context bloat:** Putting thousands of lines of RP/AC examples directly inside `SKILL.md`. All heavy guidance must use progressive disclosure (`SKILL.md` < ~120 lines pointing to topic-focused `references/*.md`).
- **Broken paths on single-skill installs:** Referring to `../../server/` directly inside `SKILL.md` without accounting for agents that copy individual skill folders into `~/.cursor/skills/` or `.github/skills/`.
- **Hallucinated Pawn signatures or constants:** Every native, callback, packet ID, and constant cited in skills/references must match upstream headers.
- **Noisy linting:** Adding speculative lint rules that trigger false positives on legitimate SA-MP anti-cheat or roleplay patterns.

---

## 3. Constraints

- **Python 3.8+ Standard Library Only:** `pawnforge`, `pawn_mcp.py`, CLI commands, and helper scripts must require zero third-party `pip` packages.
- **Cross-Platform Execution:** Must operate reliably on Windows, Linux, and macOS (handling Windows lack of symlinks cleanly, path separators, and YSI backslash include normalization).
- **Agent Skills (`agentskills.io` / Agensi) Specification:**
  - Every skill directory must contain `SKILL.md` with YAML frontmatter: `name` (1-64 chars, lowercase alphanumeric + hyphens, matching directory name) and `description` (1-1024 chars stating what it does and when to trigger).
  - Standard optional fields (`license`, `compatibility`, `metadata`) may be used; non-portable Claude-only tool names must not block other agents from loading or following instructions.
- **Backward Compatibility:** All 46 existing unit tests must continue to pass; `.claude-plugin/marketplace.json` and `plugins/pawn-forge/` must continue functioning for existing Claude Code and Antigravity users.

---

## 4. Approaches Considered

| Approach | Summary | Trade-offs | Verdict |
|---|---|---|---|
| **1. Modular Agensi Skill Suite Only** | Split into focused `SKILL.md` skills (`pawn-roleplay`, `pawn-anticheat`, `pawn-ecosystem`, etc.) with markdown references only for non-MCP agents. | Clean context usage and Agensi-ready, but Cursor/Copilot/CLI agents without MCP cannot execute the compiler, linter, or ID lookup deterministically. | Rejected |
| **2. Monolithic Master Skill** | One giant `pawn-forge` skill holding all SA-MP standards, RP, anti-cheat, ecosystem docs, and tooling. | Easy to list as 1 item, but severely bloats agent context windows; simple tasks load unrelated RakNet/RP/compiler docs. | Rejected |
| **3. Modular Agensi Skill Suite + Standalone Zero-Config CLI** | Focused modular skills at root `skills/`, backed by a portable stdlib CLI (`pawnforge`) alongside the MCP server, with unified tool-resolution instructions. | Best of both worlds: low token overhead via modular skills + deterministic compile/lint/lookup on all 20+ agents regardless of MCP support. Slightly more packaging/sync engineering. | **Selected** |

---

## 5. Detailed Design

### 5.1 Repository Layout, Agensi Discovery, and Plugin Sync

`npx skills add` and Agensi scan the repository root `skills/` directory, while Claude Code Marketplace installs `./plugins/pawn-forge` by copying that subdirectory into its plugin cache. To satisfy both without drift:

1. **Canonical Skills Directory at Repo Root (`skills/`):**
   Every skill lives under `skills/<skill-name>/` with `SKILL.md`, optional `references/`, and optional `scripts/`:
   - **Core & Workflows (refactored for portability + `pawn-*` namespacing):**
     - `skills/pawn-standards/` — Modern Pawn fundamentals (SA-MP 0.3.7 & open.mp)
     - `skills/pawn-build/` — Build-until-clean compiler workflow
     - `skills/pawn-audit/` — Security, stability, and modernization audit
     - `skills/pawn-debug-crash/` — CrashDetect & server log triage
     - `skills/pawn-migrate-openmp/` — SA-MP 0.3.7 to open.mp migration
     - `skills/pawn-modernize-storage/` — File storage (`dini`/`y_ini`) to SQLite/MySQL R41
     - `skills/pawn-test/` — Headless open.mp & YSI `y_testing` workflows
     - `skills/pawn-textdraw/` — TextDraw editor export to clean module
   - **New Domain Skills:**
     - `skills/pawn-roleplay/` — Roleplay systems architecture & exploit-free persistence
     - `skills/pawn-anticheat/` — Server-side anti-cheat & exploit defense
     - `skills/pawn-ecosystem/` — Deep guides for SA-MP/open.mp include ecosystems
2. **Global Namespace Collision Prevention (`pawn-*` prefix):**
   When installed globally across 20+ agents (`~/.agents/skills/`, `~/.cursor/skills/`, `.github/skills/`), generic names like `build`, `test`, or `audit` conflict with general language skills. Root `skills/` uses `pawn-*` names (`pawn-build`, `pawn-audit`, `pawn-test`, etc.).
3. **Syncing with `plugins/pawn-forge/skills/` (Builder Call — Backward-Compatible Rename Mapping):**
   - Do **not** rely on Git symlinks (unreliable on Windows without Developer Mode).
   - Preserve legacy Claude Code slash command names inside `plugins/pawn-forge/skills/` (`build`, `audit`, `debug-crash`, `migrate-openmp`, `modernize-storage`, `test`, `textdraw`, `pawn-standards`) and add the 3 new plugin skills as `roleplay`, `anticheat`, and `ecosystem` (so `/pawn-forge:build`, `/pawn-forge:roleplay`, etc. remain short and backward compatible).
   - Provide `plugins/pawn-forge/tools/sync_skills.py` (stdlib Python) that maps `skills/pawn-<slug>` -> `plugins/pawn-forge/skills/<slug>` (with `pawn-standards` -> `pawn-standards`), rewriting the YAML `name:` field to match the target directory name and normalizing internal cross-skill references (e.g., `pawn-audit` in `skills/` vs `audit` / `/pawn-forge:audit` in `plugins/pawn-forge/skills/`).
   - Add a unit test (`test_skills.py`) that fails if `plugins/pawn-forge/skills/` diverges from root `skills/` under this mapping or violates Agent Skills schema rules.
   - Update `README.md` Antigravity instructions to recommend `npx skills add POORSAKEN2/pawn-forge` for multi-agent skill installs or pointing `.agents/plugins/pawn-forge` at `plugins/pawn-forge/` (avoiding exposing both root `skills/` and `plugins/pawn-forge/skills/` simultaneously).

### 5.2 Standalone CLI (`pawnforge`) & Cross-Agent Tool Resolution

1. **Python Package & Entry Points (`pyproject.toml` at repo root):**
   - Zero-dependency PEP 621 `pyproject.toml` pointing package `pawnforge` at `plugins/pawn-forge/server/pawnforge` and including `plugins/pawn-forge/server/data/*.json` as package data.
   - Console entry points:
     - `pawnforge = "pawnforge.cli:main"`
     - `pawnforge-mcp = "pawnforge.mcp_entry:main"` (or invoking `pawn_mcp:main`).
   - Allows installation via `pip install git+https://github.com/POORSAKEN2/pawn-forge.git`, `pipx install ...`, `uv tool install ...`, or ad-hoc `uvx --from git+... pawnforge ...`, plus `python -m pawnforge` from any repo clone.
2. **CLI Subcommands (`plugins/pawn-forge/server/pawnforge/cli.py`):**
   Every MCP tool in `tools.py` maps 1:1 to a CLI subcommand accepting `--json` (outputs the exact JSON dict returned by `call_tool` to stdout) and default compact human-readable text:
   - `pawnforge info <project_dir>`
   - `pawnforge compile [<file> | --code <src_or_->] [--project-dir DIR] [--includes DIR...] [--output temp|alongside|PATH] [--compat] [--mode auto|pawncc|sampctl]`
   - `pawnforge install-compiler [--version VER]`
   - `pawnforge lint [<path> | --code <src_or_->] [--min-severity info|warning|error] [--rules ID...] [--exclude ID...]`
   - `pawnforge lint-rules`
   - `pawnforge analyze-log [<path> | --text -] [--source-root DIR]`
   - `pawnforge lookup <kind> [<query>] [--library LIB] [--limit N]`
   - `pawnforge api [--name NAME | --query Q] [--library LIB] [--project-dir DIR] [--limit N]`
   - `pawnforge migrate <file> [--write none|copy|in_place|return]`
   - `pawnforge textdraw [<file> | --code -] [--prefix P] [--target openmp|samp] [--ysi-hooks] [--write-to PATH]`
   - `pawnforge run-server <server_dir> [--script NAME | --amx PATH] [--timeout N] [--stop-on REGEX]`
   - Exit codes: `0` when the command succeeds (`ok` is not `False` and, for `compile` with `--strict` or `lint` with `--fail-on`, checks pass; default returns `0` with structured JSON/output when tool execution itself succeeded, `1` on fatal execution/usage error so agents parsing JSON don't treat expected compiler diagnostics as crashed tool execution, while `--check` / `--strict` returns `1` on compiler errors or lint errors for CI use).
3. **Portable Tool Invocation in `SKILL.md`:**
   Skills that require verification (`pawn-standards`, `pawn-build`, `pawn-audit`, `pawn-debug-crash`, `pawn-migrate-openmp`, `pawn-modernize-storage`, `pawn-test`, `pawn-textdraw`) replace Claude-specific MCP hints with a uniform **Tool Resolution Order**:
   1. **MCP active:** Call the Pawn Forge MCP tool directly (`compile`, `lint`, `lookup`, `api_lookup`, `project_info`, `analyze_log`, etc.).
   2. **CLI available:** Run `pawnforge <subcommand> --json` (or `python -m pawnforge <subcommand> --json`, or `python scripts/pawnforge_exec.py <subcommand> --json` if bundled, or `uvx --from git+https://github.com/POORSAKEN2/pawn-forge pawnforge <subcommand> --json`).
   3. **Direct compiler fallback:** If neither MCP nor `pawnforge` is installed yet, tell the user how to install the CLI (`pip install git+https://github.com/POORSAKEN2/pawn-forge.git`) or run `pawncc` directly if present on `PATH`/`qawno`/`pawno`, and apply the skill's static checklist manually without claiming uncompiled verification.
4. **Lightweight Bootstrapper (`scripts/pawnforge_exec.py`):**
   Each tool-dependent skill may include a small (<80 lines) `scripts/pawnforge_exec.py` that locates an existing `pawnforge` installation (`PATH`, workspace `.agents/plugins/pawn-forge/server`, `~/.claude/plugins/...`, `~/.gemini/config/plugins/...`) or executes `pawncc` directly if found, failing loudly with exact install instructions if unavailable. No duplicate ~900KB JSON bundles are copied into every skill folder.

### 5.3 New Domain Skill: `skills/pawn-roleplay/`

- **`SKILL.md`:** Concise workflow and non-negotiable engineering rules for SA-MP/open.mp roleplay servers (state ownership, race-checked async DB persistence, atomic transactions, virtual world/interior isolation, 144-char chat limits, zero-trust client input). Points to 4 focused reference files:
  1. `references/accounts-and-characters.md`:
     - Multi-character schema (`accounts` + `characters` tables), `gRace[playerid]` disconnect guard for async MySQL R41 / `samp-bcrypt`.
     - Dirty-flag / batch-save lifecycle (`Character_MarkDirty` + periodic staggered timer `ptask` vs immediate persistence for cash, inventory, bans, and admin logs).
     - Safe spawn state machine (login -> character select -> spawn freeze + `Streamer_UpdateEx` -> unfreeze).
  2. `references/inventory-and-items.md`:
     - Normalized `character_items` relational table vs brittle delimited strings.
     - Static item registry `enum` + metadata array (`ItemInfo[MAX_ITEM_TYPES]`: name, max stack, weight, category, flags).
     - Duplication-proof atomic transfers (`Inventory_TransferItem`, locking trade/container slots during async saves or disconnects, validating `slot`/`amount > 0` and integer overflow).
  3. `references/vehicles-and-properties.md`:
     - **Dynamic Vehicles:** Separating runtime `vehicleid` (`1..MAX_VEHICLES`) from persistent SQL `db_id`, tracking fuel, engine/lights/lock via `GetVehicleParamsEx`/`SetVehicleParamsEx`, trunk/glovebox capacity, `OnVehicleDeath`/`OnVehicleSpawn` state preservation, avoiding `MAX_VEHICLES` leakage.
     - **Houses & Businesses:** Dynamic pickup + 3D text label + Streamer area entrypoints, deterministic virtual world allocation (`VW_HOUSE_BASE + houseid`), interior coordinate lookup (`lookup kind=interior`), key sharing, safe/till balance locking.
  4. `references/factions-economy-chat.md`:
     - **Factions & Jobs:** `enum` faction types (LEO, EMS, Gov, Illegal), rank arrays, duty state toggles (saving civilian skin/weapons before issuing duty loadout), radio channel isolation, locker validation.
     - **Economy Safety:** Integer overflow checks (`amount <= 0`, `cash > cellmax - amount`, `MAX_SAFE_MONEY` cap `1_000_000_000`), atomic `Money_Transfer(from, to, amount)` helper, audit log insertion.
     - **RP Chat & Proximity:** `Chat_SendProximity(playerid, Float:radius, color, const msg[], ...)` checking `IsPlayerConnected`, same `GetPlayerVirtualWorld` and `GetPlayerInterior`, distance via `GetPlayerPos` / `VectorSize` (never looping `MAX_PLAYERS` without `foreach`), plus clean 144-char two-line wrapping for long `/me` and `/do` actions.

### 5.4 New Domain Skill: `skills/pawn-anticheat/`

- **`SKILL.md`:** Core threat model and defense-in-depth rules for SA-MP 0.3.7 and open.mp (server-authoritative state, lag-tolerant grace windows, never kicking immediately before RPC delivery, verifying all client callbacks). Points to 3 reference files:
  1. `references/server-authoritative-state.md`:
     - **Cash AC:** Server-side `sPlayerCash[MAX_PLAYERS]` as single source of truth; `AC_GivePlayerMoney`/`AC_ResetPlayerMoney`; `EnableStuntBonusForAll(false)` & vending/casino strategy; detecting client cash desync without false-banning lag.
     - **Weapon & Ammo AC:** Server-side `sPlayerWeapons[MAX_PLAYERS][13]` & `sPlayerAmmo[MAX_PLAYERS][13]` synced via `GetWeaponSlot`; grace timer (`sWeaponGraceUntil[playerid]`) after `AC_GivePlayerWeapon`, `AC_ResetPlayerWeapons`, or spawn; handling legitimate vehicle-entry weapons (Shotgun in Police Car, Golf Club in Caddy, Parachute in aircraft) and `WEAPON_PARACHUTE` / `WEAPON_CAMERA` edge cases.
     - **Health & Armour AC:** Server-side HP/Armour tracking (`sPlayerHealth`, `sPlayerArmour`), disabling client-side damage healing exploits (vending machines, vehicle repair pickups), `SetPlayerTeam` unified-team server-side damage pipeline vs tolerance-based detection.
  2. `references/movement-and-combat.md`:
     - **Movement / Speed / Airbreak / Teleport:** Tick-delta distance calculation using `GetTickCount()`, ignoring ticks during `Streamer_UpdateEx` / server-initiated `AC_SetPlayerPos` / `AC_PutPlayerInVehicle` grace windows, differentiating vehicle top speeds, passenger states (`PLAYER_STATE_PASSENGER`), surfing (`GetPlayerSurfingVehicleID`), and falling Z-velocity (`GetPlayerVelocity`).
     - **Combat & Hit Validation:** `OnPlayerWeaponShot` (SA-MP 0.3z+ / open.mp) checks — invalid `hittype`, `fHitPos` distance/NaN checks (`floatcmp` / NaN `val != val`), rapid-fire/C-bug cooldown per weapon ID, ammo depletion check. `OnPlayerGiveDamage` / `OnPlayerTakeDamage` cross-validation and fake-kill rejection in `OnPlayerDeath`.
     - **Dialog, Input & State Anti-Spoofing:** Server-tracked `sActiveDialog[playerid]` checked in `OnDialogResponse` (preventing client-forged `dialogid` packet injection), server-side range/state re-verification on dialog submit (e.g., player walked away from ATM before clicking "Withdraw"), empty `strcmp` pitfall (`!isnull(inputtext)`), and delayed `Kick` (`defer KickPlayer(playerid)` / `SetTimerEx`) so kick reasons reach the client.
  3. `references/raknet-and-nexac.md`:
     - **Pawn.RakNet Defenses:** Intercepting `OnIncomingPacket` (`ID_PLAYER_SYNC = 207`, `ID_VEHICLE_SYNC = 200`, `ID_PASSENGER_SYNC = 211`, `ID_BULLET_SYNC = 206`) and `OnIncomingRPC` (`RPC_DialogResponse = 62`, `RPC_ClickPlayer = 23`, `RPC_Death = 53`, `RPC_DamageVehicle = 106`, `RPC_ScmEvent = 96`) to drop NaN/Inf quaternions/positions, invalid seat IDs, passenger-crashers, trailer-crashers, and spoofed `GiveTakeDamage` RPCs.
     - **Nex-AC & Existing AC Integration:** Include ordering requirements (`#include <nex-ac>` after libraries it hooks, before gamemode modules), forwarding `OnCheatDetected`, whitelisting custom teleports/weapons via Nex-AC hooks rather than fighting it.

### 5.5 New Domain Skill: `skills/pawn-ecosystem/`

- **`SKILL.md`:** Ecosystem selector and integration rules (include ordering, SA-MP 0.3.7 plugin vs open.mp component differences, header verification via `api_lookup`). Points to 5 focused reference files:
  1. `references/pawn-raknet.md`: BitStream lifecycle (`BS_New` / `BS_Delete`, `BS_ResetReadPointer`, `BS_ReadValue`, `BS_WriteValue`), `OnIncomingPacket`, `OnIncomingRPC`, `OnOutgoingRPC`, typed `PR_*` handlers (`IRPC:62`, `IPacket:207`), `PR_SendPacket`/`PR_SendRPC`, and common sync packet layouts.
  2. `references/ysi5-deep-dive.md`: Advanced YSI 5 patterns (`y_inline`, `y_inline_mysql`, `y_inline_timers`, `y_dialog`, `y_va`, `y_bits`, `y_groups`, `y_master`), include ordering (`<open.mp>` / `<a_samp>` -> plugins -> YSI), and memory/compile-time options (`YSI_NO_HEAP_MALLOC`, `YSI_NO_OPTIMISATION_MESSAGE`).
  3. `references/streamer-and-world.md`: Streamer tuning (`Streamer_SetMaxItems`, `Streamer_SetVisibleItems`, `Streamer_SetTickRate`, `Streamer_SetCellDistance`), dynamic areas (`CreateDynamicPolygon`, `Circle`, `Sphere`, `Cuboid`), player/vehicle attachments (`AttachDynamicObjectToVehicle`, `AttachDynamicAreaToPlayer`), per-player visibility (`E_STREAMER_PLAYER_ID`), and `Streamer_UpdateEx`.
  4. `references/colandreas-and-physics.md`: **ColAndreas** (`CA_Init`, `CA_RayCastLine`, `CA_RayCastLineEx`, `CA_FindZ_For2DCoord`, `CA_CreateObject` synchronization with Streamer maps for custom interiors/maps, line-of-sight for anti-cheat and RP visibility) and **MapAndreas** lightweight height-map fallback.
  5. `references/auth-and-commands.md`: **samp-bcrypt** (`bcrypt_hash`, `bcrypt_verify`, `bcrypt_is_equal`, cost factor 10-12, race-checked callbacks), **Pawn.CMD** vs **YCMD** vs **I-ZCMD** patterns, **sscanf2** advanced specifiers (`k<weapon>`, `k<vehicle>`, `e<enum>`, `p<delim>`, `q`), and **easyDialog** / **mSelection** patterns.

### 5.6 Tooling, Reference Data, and Lint Rule Enhancements

1. **`project.py` Library Detection:**
   Extend `libraries_detected` in `project_info` to detect: `pawn.raknet`, `colandreas`, `mapandreas`, `samp-bcrypt`, `nex-ac`, `easydialog`, `mselection`, `izcmd`.
2. **Conservative New Lint Rules (`lint.py`):**
   - `PF701` (warning, `reliability`/`security`): Immediate `Kick(` or `Ban(`/`BanEx(` in the same block right after `SendClientMessage` or `ShowPlayerDialog` without a timer delay (SA-MP/open.mp drops queued packets on immediate kick).
   - `PF702` (error, `security`): Empty-string `strcmp` vulnerability on `inputtext` or user parameters (`!strcmp(inputtext, ...)` / `strcmp(inputtext, ...) == 0` without checking `isnull` or `strlen(inputtext)` / `!inputtext[0]` — in Pawn `string.inc`, `strcmp("secret", "")` returns `0`!).
   - `PF703` (warning, `security`): `OnPlayerWeaponShot`, `OnPlayerGiveDamage`, or `OnPlayerTakeDamage` indexing an array with `weaponid`, `damagedid`, or `issuerid` without checking bounds (`INVALID_PLAYER_ID` / `0 <= weaponid < ...`), risking crashdetect Error 4 via spoofed packets.
   - `PF704` (error, `security`): `SendRconCommand` called with an unvalidated `format()` buffer built from `%s` (RCON injection risk).
   - `PF801` (warning, `ecosystem`): `Pawn.RakNet` `BS_New()` / `BS_NewCopy()` without a matching `BS_Delete()` in the function (BitStream native memory leak).
   - `PF802` (info, `performance`): `IsPlayerInRangeOfPoint` inside `OnPlayerUpdate` (should use Streamer dynamic areas or throttled checks).
3. **Reference Data Expansion & Regeneration (`tools/build_data.py`, `server/data/`, `api.py` — Builder Call):**
   - **Canonical upstream sources added to `tools/build_data.py`:**
     - `samp-stdlib`: `pawn-lang/samp-stdlib` (0.3.7-R2: `a_samp.inc`, `a_players.inc`, `a_vehicles.inc`, `a_objects.inc`, `a_http.inc`, `a_sampdb.inc`, `a_npc.inc`)
     - `pawn.raknet`: `katursis/Pawn.RakNet` (`Pawn.RakNet.inc`; compatible across SA-MP 1.5.x and open.mp `1.6.x-omp` component releases)
     - `samp-bcrypt`: `Sreyas-Sreelal/samp-bcrypt` (`samp_bcrypt.inc`, the standard SA-MP/open.mp bcrypt plugin; `lassir/bcrypt-samp`'s `bcrypt.inc` is documented as an alternative in `pawn-ecosystem` and indexed via `project_dir` when present)
     - `colandreas`: `Pottus/ColAndreas` (`Server/include/colandreas.inc`)
   - **Regenerate `server/data/*.json` during implementation:** Fetch upstream headers during build and regenerate `natives.json`, `callbacks.json`, and `sources.json` (preserving/pinning the existing 6 upstream repositories alongside the 4 new ones with exact commit hashes in `sources.json`). `MapAndreas`, `easyDialog`, and `mSelection` are documented in `pawn-ecosystem`, detected in `project.py`, and indexed from the user's `project_dir` via `api_lookup`.
   - **`api_lookup` platform filtering & `open.mp` / `samp-stdlib` collision resolution:**
     - Add an optional `platform` parameter (`"auto" | "open.mp" | "sa-mp"`, default `"auto"`) to `api_lookup` (and `--platform` to `pawnforge api`).
     - When `project_dir` and `library` are both omitted and `platform="auto"`, exclude `samp-stdlib` by default so `open.mp` remains the default without ~300 duplicate symbols (preserving `ApiTest.test_deprecated`).
     - When `platform` resolves to `"sa-mp"` (via `project_info` or explicit `--platform sa-mp`), filter out `open.mp` stdlib entries, include `samp-stdlib`, and suppress `openmp_deprecation` warnings so SA-MP 0.3.7 users are not shown open.mp-only natives like `TextDrawColour`.
     - Improve `project.detect_platform` to fall back to scanning project `.inc`/`.pwn` files under `include/`/`includes/`/`src/` when `main_script` delegates includes and lacks direct `<open.mp>` / `<a_samp>` lines.

### 5.7 Verification & Testing Plan

- **Unit Tests:**
  - `test_lint.py`: Add fixture entries in `tests/fixtures/legacy_bad.pwn` and dedicated unit tests for `PF701`–`PF704` and `PF801`–`PF802` (verifying both positive detections and clean-code silence).
  - `test_cli.py`: Test every `pawnforge` CLI subcommand (`info`, `lint`, `lint-rules`, `lookup`, `api`, `analyze-log`, `migrate`, `textdraw`) in `--json` and text modes, verifying parity with `tools.call_tool()`.
  - `test_skills.py`: Validate all skills in `skills/` and `plugins/pawn-forge/skills/` against the Agent Skills schema (`name`, `description` length/format, relative markdown reference links resolve, zero broken paths, and `skills/` <-> `plugins/pawn-forge/skills/` sync check passes).
  - `test_tools.py`: Test extended `project_info` library detections.
- **Compiler Integration Tests (`test_integration.py`):**
  - Add compilable `doc_snippets/` for Roleplay, Anti-Cheat, and Ecosystem patterns (`rp_inventory.pwn`, `rp_vehicle_house.pwn`, `ac_weapons_cash.pwn`, `ac_dialogs_kick.pwn`, etc.) compiled via `compile_pawn` when `PAWNFORGE_PAWNCC` + `PAWNFORGE_TEST_INC` are configured.

---

## 6. Decisions Left to the Builder / Pending Confirmation

1. **Left to the Builder:**
   - Exact layout of `cli.py` argparse subparsers and human-readable text formatters.
   - Internal structure of `scripts/pawnforge_exec.py` and `tools/sync_skills.py`.
   - Specific prose and helper code structuring inside individual `references/*.md` files, provided all Pawn code obeys `pawn-standards` and compiles cleanly where tested.
2. **Settled Engineering & Product Calls (Check During Spec Review):**
   - **Skill naming & backward-compatible sync:** Root `skills/` uses `pawn-*` names (`pawn-build`, `pawn-audit`, `pawn-roleplay`, etc.) for collision-free Agensi/global installs; `plugins/pawn-forge/skills/` preserves legacy short slash-command names (`build`, `audit`, `roleplay`, `anticheat`, `ecosystem`, etc.) via an explicit mapping in `tools/sync_skills.py` enforced by `test_skills.py`.
   - **Canonical upstream sources & data regeneration:** Index `pawn-lang/samp-stdlib`, `katursis/Pawn.RakNet`, `Sreyas-Sreelal/samp-bcrypt` (`samp_bcrypt.inc`), and `Pottus/ColAndreas` (`colandreas.inc`) in `tools/build_data.py` and regenerate `server/data/*.json` during implementation; cover `lassir/bcrypt-samp`, `MapAndreas`, `easyDialog`, and `mSelection` in `pawn-ecosystem` docs + `project_info` + dynamic `project_dir` scanning.
   - **`api_lookup` platform filtering:** Default to `open.mp` (excluding `samp-stdlib` duplicates) when no project/library/platform is specified; hide `open.mp` stdlib and `openmp_deprecation` notices when `sa-mp` is detected or passed via `--platform sa-mp`.
   - **Data bundling:** Keep `server/data/*.json` (~900 KB) inside the Python package (`pyproject.toml`) rather than duplicating JSON files inside all 11 skill folders.
