---
name: pawn-standards
description: Modern, safe Pawn for SA-MP 0.3.7 and open.mp game servers, including YSI, Streamer, MySQL R41, sscanf, Pawn.CMD, Pawn.RakNet, samp-bcrypt, and ColAndreas. Use when writing, reviewing, refactoring, or explaining Pawn (.pwn/.inc) gamemodes, filterscripts, or includes.
license: MIT
compatibility: Optional Python 3.8+ for pawnforge CLI / MCP verification and pawncc 3.10.x compiler.
metadata:
  author: POORSAKEN2
  version: "0.2.0"
---

# Writing Pawn the modern way

Treat 2008-2014 forum habits (`strtok`, `dini`, `format()` SQL, `new string[256]`, magic IDs) as suspect. Verify every signature, ID, and build instead of guessing.

## Tool Resolution Order

Use the first available tier for any verification tool:
1. **Pawn Forge MCP** (if connected): `project_info`, `compile`, `lint`, `api_lookup`, `lookup`, `install_compiler`, `convert_textdraws`.
2. **Standalone CLI**: `pawnforge <cmd> --json` (or `python scripts/pawnforge_exec.py <cmd> --json`, `python -m pawnforge <cmd> --json`, or `uvx --from git+https://github.com/POORSAKEN2/pawn-forge pawnforge <cmd> --json`).
3. **Fallback**: run `pawncc` directly or review manually, and suggest `pip install git+https://github.com/POORSAKEN2/pawn-forge.git`.

## 1. Verify, never recall

| Need | MCP tool / CLI command |
|---|---|
| Unfamiliar project | `project_info` / `pawnforge info <dir> --json` (platform, libraries, includes, compiler) |
| Does it compile? | `compile` / `pawnforge compile <file> --json` after **every** change until clean |
| Native or callback signature | `api_lookup` / `pawnforge api --name <sym> --platform <auto\|open.mp\|sa-mp> --project-dir <dir> --json` (covers `open.mp`, `samp-stdlib`, `streamer`, `mysql-r41`, `sscanf`, `pawn.cmd`, `pawn.raknet`, `samp-bcrypt`, `colandreas`) |
| Vehicle / skin / weapon / interior / anim ID | `lookup` / `pawnforge lookup <kind> <query> --json` (never guess IDs or anim names) |
| Static safety / leak / legacy check | `lint` / `pawnforge lint <path> --json` |

If no compiler is found, report it and offer `install_compiler` / `pawnforge install-compiler`; do not silently skip compilation.

## 2. Pick the target, then stay consistent

`project_info` / `pawnforge info` reports `platform` (`open.mp` or `sa-mp`).

- **open.mp** (default for new work): `#include <open.mp>`, British spellings (`TextDrawColour`), `DB_*` SQLite natives, tagged constants (`true`/`false`, `WEAPON_DEAGLE`, `TEXT_DRAW_FONT_*`, `TEXT_DRAW_ALIGN_*`, `Float:` literals), tagged callback headers from `api_lookup` (`platform="open.mp"`), and direct format args (`SendClientMessage(playerid, -1, "Hi %s", name)`).
- **SA-MP 0.3.7** (first-class support): `#include <a_samp>`, SA-MP spellings/natives (`TextDrawColor`, `db_*`), verify headers with `api_lookup` (`platform="sa-mp"`), and compile with `compat: true` (`--compat` / `-Z`) if legacy includes require it. Every safety, DB, command, loop, and structure rule below still applies.

## 3. Strings and buffers

- Pass the destination's own size: `format(msg, sizeof msg, ...)`, never a literal or another buffer's `sizeof`.
- Size buffers to real limits, not `256`: chat output `144`, chat/command input `128`, dialog caption `64`, dialog input `128`, dialog body `4096`, player name `MAX_PLAYER_NAME + 1`.
- Never `dest = src` for differently sized strings (error 047). Use `strcopy(dest, src)` on open.mp or `strcat((dest[0] = EOS, dest), src)` on SA-MP.
- Mark read-only array params `const` (warnings 214/239): `stock Greet(const name[])`.
- Never pass user text as a format string: `SendClientMessage(playerid, -1, "%s", inputtext)`.
- Make large locals (>1-2 KB) `static`/global or raise `#pragma dynamic`; watch `compile` `stack` output.
- Details: [references/strings-and-buffers.md](references/strings-and-buffers.md)

## 4. Data storage

- Never use `dini`/`dfile`/`dudb`/`DOF2`/`y_ini` for accounts. Use MySQL R41 or SQLite (`pawn-modernize-storage`).
- MySQL R41: `mysql_tquery` + callback, `mysql_format` with `%e` for every quoted value (`%d`/`%f` for numbers); avoid blocking `mysql_query`. Race-check async callbacks against disconnect/reconnect. Details: [references/mysql-r41.md](references/mysql-r41.md)
- SQLite: escape quoted values with `%q` and free **every** result with `DB_FreeResultSet` (`db_free_result` on SA-MP), including UPDATE/INSERT.
- R41 has no server-side prepared statements; `mysql_format` + `%e` (or ORM API) is the safe parameterisation.
- Passwords: `samp-bcrypt`. Never `udb_hash`, Whirlpool, MD5, or `SHA256_PassHash`.

## 5. Commands and input

- Use Pawn.CMD (`cmd:name(playerid, params[])`, `alias:`, `flags:`) or YSI `YCMD:name(playerid, params[], help)`, never `strtok`/`strcmp` chains in `OnPlayerCommandText`.
- Parse with `sscanf2`: every `s` needs `[size]`; `u` yields `INVALID_PLAYER_ID` when unmatched—always check it.
- Validate all client input: `dialogid`, `listitem` bounds, `inputtext` non-empty/length (guard `strcmp` against empty `inputtext`), connected targets, and combat IDs. Details: [references/commands-and-input.md](references/commands-and-input.md)

## 6. Loops, timers, entities

- Iterate players with `foreach (new i : Player)` (`y_iterate`). `GetPlayerPoolSize` is deprecated on open.mp; fallback loop is `i < MAX_PLAYERS`.
- Store every repeating timer ID and `KillTimer` on disconnect, or use `y_timers` `ptask`/`task`/`defer`.
- Create TextDraws/labels/pickups once and destroy on cleanup; convert editor exports with `pawn-textdraw`.
- Use Streamer (`CreateDynamicObject`, areas, CPs) for maps; call `Streamer_UpdateEx` before teleporting onto mapped floors. Details: [references/streamer.md](references/streamer.md)
- Keep `OnPlayerUpdate` trivial: no queries, file I/O, player loops, or `IsPlayerInRangeOfPoint` polling.

## 7. Structure & legacy code

- Split gamemodes into `includes/<system>.inc` with `static` state, `enum` dialog IDs, and YSI `hook` callbacks ([references/ysi.md](references/ysi.md)). Compile with `-d3` + CrashDetect in dev.
- Legacy quick map: [references/legacy-to-modern.md](references/legacy-to-modern.md). Fix what the task touches, note the rest, and offer `pawn-audit` or `pawn-migrate-openmp`.
