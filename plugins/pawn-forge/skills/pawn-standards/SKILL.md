---
name: pawn-standards
description: Modern, safe Pawn for SA-MP and open.mp game servers. Use whenever writing, reviewing, refactoring or explaining Pawn (.pwn/.inc) gamemodes, filterscripts or includes, including YSI, Streamer, MySQL R41, sscanf and Pawn.CMD code. Replaces outdated 2008-2014 SA-MP forum habits with verified current practice.
when_to_use: Any task touching .pwn or .inc files, SA-MP/open.mp scripting questions, "write a command/system/gamemode", reviewing Pawn snippets, choosing Pawn libraries.
paths: "**/*.pwn, **/*.inc, **/pawn.json"
user-invocable: false
---

# Writing Pawn the modern way

Most public Pawn code is 2008-2014 SA-MP forum code: `strtok` commands, `dini` accounts, `format(query, ..., "%s")`
SQL, `new string[256]` everywhere, magic-number IDs. Treat any instinct that looks like that as suspect.
pawn-forge gives you tools so you never have to guess. Use them.

## 1. Verify, never recall

| Need | Do this |
|---|---|
| Does it compile? | `compile` (file or `code`) after **every** change. Iterate until `ok` and ideally `clean`. Never present Pawn you have not compiled when a compiler is available. |
| Exact native/callback signature | `api_lookup name=...` (pass `project_dir` to use the project's own include versions) |
| Vehicle / skin / weapon / interior / animation ID | `lookup kind=...`. Never type an ID or animation name from memory. |
| Is this safe / leaky / legacy? | `lint` the file or snippet |
| Unfamiliar project | `project_info` first: platform, libraries, include dirs, compiler |

If no compiler is found, say so and offer `install_compiler`; do not silently skip verification.

## 2. Pick the target, then stay consistent

`project_info` reports `platform`. For **open.mp** (default for new work):
- `#include <open.mp>` (not `<a_samp>`), British spellings (`TextDrawColour`), `DB_*` SQLite natives.
- Use tagged constants: `true/false` for `bool:`, `WEAPON_DEAGLE` not `24`, `TEXT_DRAW_FONT_*`, `TEXT_DRAW_ALIGN_*`, `Float:` literals with a decimal point.
- Callbacks have tagged parameters, e.g. `OnPlayerDeath(playerid, killerid, WEAPON:reason)`. Copy the header from `api_lookup`.
- Many natives take format arguments directly: `SendClientMessage(playerid, -1, "Hi %s", name)`.

For **SA-MP 0.3.7** keep `a_samp` names, but every other rule here still applies.

## 3. Strings and buffers (where most crashes come from)

- A string is an array of cells, NUL-terminated. `sizeof(arr)` is its capacity in cells.
- Always pass the size of **the destination itself**: `format(msg, sizeof msg, ...)`, never a literal or another buffer's `sizeof`.
- Size buffers to real limits, not `256`: chat output 144, chat/command input 128, dialog caption 64, dialog input 128, dialog body 4096, player name `MAX_PLAYER_NAME + 1`.
- Never `dest = src` for strings of different sizes (error 047). Use `strcopy(dest, src)` (open.mp) or `strcat((dest[0] = EOS, dest), src)` on SA-MP.
- Mark read-only array parameters `const` (fixes warnings 214/239): `stock Greet(const name[])`.
- Never pass user text as a format string: `SendClientMessage(playerid, -1, "%s", inputtext)`, not `SendClientMessage(playerid, -1, inputtext)` when formatting is active.
- Large buffers (> ~1-2 KB) in hot callbacks: make them `static` or global, or raise `#pragma dynamic`. Check the `stack` field of `compile` output.
- Details and patterns: [references/strings-and-buffers.md](references/strings-and-buffers.md)

## 4. Data storage

- **Never** `dini`/`dfile`/`dudb`/`DOF2`/y_ini for accounts. Use MySQL R41 or SQLite (built in). See the `modernize-storage` skill.
- MySQL R41: `mysql_tquery` + callback, `mysql_format` with `%e` for every quoted value, `%d`/`%f` for numbers. `mysql_query` blocks the whole server; avoid it. Guard async callbacks against the player having left (race-check counter). Details: [references/mysql-r41.md](references/mysql-r41.md)
- SQLite: escape quoted values with `%q` (`format` and `DB_ExecuteQuery` format arguments). Free **every** result with `DB_FreeResultSet`, including UPDATE/INSERT results.
- R41 has no server-side prepared statements; `mysql_format` + `%e` (or the ORM API) is the safe parameterisation. Say this plainly if asked for "prepared statements".
- Passwords: bcrypt (samp-bcrypt plugin). Never `udb_hash`, Whirlpool, MD5 or `SHA256_PassHash` (deprecated by open.mp itself).

## 5. Commands and input

- Commands: Pawn.CMD (`cmd:name(playerid, params[])`, `alias:`, `flags:`) or YSI `YCMD:name(playerid, params[], help)`. Never `strtok`/`strcmp` chains in `OnPlayerCommandText`.
- Parse with sscanf2: `if (sscanf(params, "us[64]", target, reason)) return SendClientMessage(playerid, -1, "Usage: /kick [player] [reason]");`
  Every `s` needs a size. `u` yields `INVALID_PLAYER_ID` when no player matches: always check it.
- Validate everything from the client: `listitem` ranges, `inputtext` length and content, that the dialog you are handling is the one you showed, target IDs are connected.
- Details: [references/commands-and-input.md](references/commands-and-input.md)

## 6. Loops, timers, entities

- Iterate players with `foreach (new i : Player)` (YSI y_iterate). `GetPlayerPoolSize` is deprecated on open.mp; if you must loop slots use `i < MAX_PLAYERS`.
- Store every repeating timer ID and `KillTimer` it on disconnect, or use y_timers `ptask`/`task`/`defer`.
- Create TextDraws, labels and pickups once and destroy them when done; never create per spawn without destroying. Use `convert_textdraws` for editor exports.
- Maps and many objects: Streamer (`CreateDynamicObject`, areas, CPs). Call `Streamer_UpdateEx` before teleporting onto mapped floors. Details: [references/streamer.md](references/streamer.md)
- Keep `OnPlayerUpdate` trivial: no queries, file I/O or player loops.

## 7. Structure

- Split gamemodes into modules (`includes/<system>.inc`) with `static` module state and a small public API.
- With YSI, hook callbacks per module (`hook OnPlayerConnect(playerid)`) instead of one giant callback. Details: [references/ysi.md](references/ysi.md)
- Name dialog IDs with an `enum`; never reuse magic numbers across systems.
- Compile with `-d3` and load CrashDetect in development so runtime errors have file:line backtraces.

## Legacy to modern quick map

See [references/legacy-to-modern.md](references/legacy-to-modern.md) for a full table. When you meet legacy code, fix what
the task touches, mention the rest, and offer the `audit` or `migrate-openmp` workflow rather than rewriting unasked.
