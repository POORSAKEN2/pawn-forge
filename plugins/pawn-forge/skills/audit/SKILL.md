---
name: audit
description: Security, stability, anti-cheat, and modernisation audit of a SA-MP or open.mp Pawn codebase (buffer overflows, SQL injection, weak hashing, input/combat/RCON exploits, leaks, legacy libraries, invalid game IDs). Use when asked to audit, review, harden, or assess a gamemode or filterscript.
license: MIT
compatibility: Optional Python 3.8+ for pawnforge CLI / MCP static analysis.
metadata:
  author: POORSAKEN2
  version: "0.2.0"
argument-hint: "[path]"
---

# Audit a Pawn codebase

Scope: target file or directory (default: current working directory).

## Tool Resolution

1. **Pawn Forge MCP**: `project_info`, `lint`, `lint_rules`, `api_lookup`, `lookup`.
2. **Standalone CLI**: `pawnforge <cmd> --json` (or `python scripts/pawnforge_exec.py <cmd> --json`, `python -m pawnforge <cmd> --json`, or `uvx --from git+https://github.com/POORSAKEN2/pawn-forge pawnforge <cmd> --json`).
3. **Fallback**: review files manually against the checklist below; suggest `pip install git+https://github.com/POORSAKEN2/pawn-forge.git`.

## Workflow

1. **Survey** with `project_info` / `pawnforge info <dir> --json` (platform, libraries, layout).
2. **Static analysis** with `lint` / `pawnforge lint <path> --json` (third-party include dirs are skipped by default; inspect rules via `lint_rules` / `pawnforge lint-rules --json` if needed). For >50 files, scan by module or delegate batches if subagents are available.
3. **Verify before reporting.** Open the source line of every `error` and `security` finding to confirm it is real; drop false positives and note any rule misfire.
4. **Manual review** beyond the linter across account/login, admin, economy, dialogs, combat, RakNet, and `OnPlayerUpdate`:
   - `OnDialogResponse`: `dialogid` checked, `listitem` bounded, `inputtext` non-empty and length-checked; no unguarded `strcmp` on `inputtext` (`PF702`, where `strcmp("pw", "") == 0`).
   - Admin & RCON: permission checked on every path (or centrally in `OnPlayerCommandReceived`); no unvalidated `%s` passed into `SendRconCommand` (`PF704`).
   - Economy & combat: client values (`inputtext`, `params`, `weaponid`, `damagedid`, `issuerid`, `hitid`) bounded before `GivePlayerMoney` or array indexing (`PF703`); `Kick`/`Ban` delayed after messages or dialogs so packets flush (`PF701`).
   - Passwords & DB: hashed with `samp-bcrypt` (no `PF203` weak hashes); SQL escaped via `%e` / `%q` (`PF201`/`PF202`).
   - Cleanup & ecosystem: timers killed on disconnect, per-player state reset, async query callbacks race-checked, RakNet `BitStream` freed with `BS_Delete` (`PF801`), no `IsPlayerInRangeOfPoint` polling in `OnPlayerUpdate` (`PF802`/`PF504`).
   - For deep system reviews, pair with `roleplay` (economy, factions, properties, persistence) and `anticheat` (server-authoritative combat, movement, RPC/RakNet validation), plus `pawn-standards` for idioms.
5. **Report** in priority order with `file:line`, concrete failure mode (crash, exploit, leak), and fix (group repeated findings per rule):
   - **Critical**: memory safety (`PF101`/`PF102`/`PF104`/`PF105`), SQL injection (`PF201`/`PF202`), auth/RCON exploits (`PF702`, `PF704`).
   - **High**: delayed kick, combat bounds, BitStream/timer/TextDraw/cache leaks, blocking queries (`PF302`–`PF304`, `PF401`–`PF405`, `PF504`, `PF701`, `PF703`, `PF801`), weak hashing (`PF203`), invalid IDs (`PF601`–`PF604`).
   - **Modernisation**: legacy libraries and patterns (`PF3xx`/`PF5xx`, `PF802` info) with migration path (`modernize-storage`, `migrate-openmp`).
6. **Offer** to fix Critical/High items and write `PAWN_AUDIT.md`; wait for confirmation before editing.
