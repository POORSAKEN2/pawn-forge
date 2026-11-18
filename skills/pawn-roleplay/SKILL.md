---
name: pawn-roleplay
description: Architecture and production-safe Pawn patterns for SA-MP 0.3.7 and open.mp roleplay servers, covering multi-character accounts, bcrypt authentication, atomic inventory/item systems, persistent vehicles and properties, factions, overflow-safe economy, and 144-char proximity chat. Use when designing, building, refactoring, or auditing roleplay gamemode systems.
license: MIT
compatibility: Optional Python 3.8+ for pawnforge CLI / MCP verification and pawncc 3.10.x compiler.
metadata:
  author: POORSAKEN2
  version: "0.2.0"
---

# Roleplay Systems in Modern Pawn

Build roleplay servers around server-authoritative memory, race-checked async persistence, and atomic transactions. Follow `pawn-standards` for baseline Pawn safety and pair combat, movement, or RakNet checks with `pawn-anticheat`.

## Tool Resolution Order

Use the first available tier for any verification tool:
1. **Pawn Forge MCP** (if connected): `project_info`, `compile`, `lint`, `api_lookup`, `lookup`.
2. **Standalone CLI**: `pawnforge <cmd> --json` (or `python scripts/pawnforge_exec.py <cmd> --json`, `python -m pawnforge <cmd> --json`, or `uvx --from git+https://github.com/POORSAKEN2/pawn-forge pawnforge <cmd> --json`).
3. **Fallback**: inspect signatures in local `.inc` files, compile with `pawncc`, and suggest `pip install git+https://github.com/POORSAKEN2/pawn-forge.git`.

Verify every native signature (`api_lookup` / `pawnforge api`) and every vehicle, skin, weapon, interior, or animation ID (`lookup` / `pawnforge lookup`) before writing code.

## Non-Negotiable RP Engineering Rules

1. **Single source of truth in server memory.** Keep cash, bank balance, inventory, vehicle ownership, property state, and faction rank in server `enum` arrays (`gChar`, `gVeh`, `gHouse`). Sync the client HUD with `ResetPlayerMoney` + `GivePlayerMoney`; never read `GetPlayerMoney` or client state as authoritative.
2. **Race-checked async persistence.** Use MySQL R41 (`mysql_tquery`, `%e` in `mysql_format`) or SQLite (`%q` + `DB_FreeResultSet` / `db_free_result`); migrate legacy `.ini` stores via `pawn-modernize-storage`. Increment `gRace[playerid]` on connect and disconnect, and verify `race == gRace[playerid] && IsPlayerConnected(playerid)` in every async MySQL and `samp-bcrypt` callback. Stagger dirty-flag auto-saves; write economy, inventory, and ownership mutations immediately.
3. **Atomic inventory & money transfers.** Guard every transfer with trade/save-lock flags (`E_CHAR_INV_LOCKED`). Validate bounds, slots, weight, and `MAX_SAFE_MONEY = 1_000_000_000` (`cash > cellmax - amount` overflow guard) before mutating arrays or writing SQL.
4. **Virtual-world & interior isolation.** Separate shared interior models by virtual world (`VW_HOUSE_BASE + houseDbId`). Set `SetPlayerVirtualWorld` and `SetPlayerInterior` **before** `SetPlayerPos`, and call `Streamer_UpdateEx` before teleporting onto mapped floors. Use Streamer dynamic areas instead of `OnPlayerUpdate` range polling (`pawn-ecosystem`).
5. **144-char chat line wrapping.** Filter proximity chat (`/me`, `/do`, `/s`, `/w`, `/b`) by `GetPlayerPos` + `VectorSize`, matching `GetPlayerVirtualWorld` and `GetPlayerInterior`. Split messages exceeding 144 characters cleanly across two lines at a word boundary.
6. **Zero-trust input & delayed disconnect.** Name dialog IDs with an `enum`; validate `dialogid`, `listitem` bounds, `isnull(inputtext)` before `strcmp`, `sscanf2` string sizes (`s[n]`), and `INVALID_PLAYER_ID` targets. Delay `Kick`/`Ban` via `SetTimerEx`/`defer` so queued messages flush (`pawn-audit`). Verify changes with `pawn-build` and `pawn-test`.

## SA-MP 0.3.7 vs open.mp

- **open.mp** (default for new servers): `#include <open.mp>`, tagged types (`bool:`, `WEAPON:`, `PLAYER_STATE:`), `strcopy(dest, src)`, `SetVehicleParamsEx` optional `-1` defaults, and direct formatting in `SendClientMessage` / `ShowPlayerDialog`.
- **SA-MP 0.3.7**: `#include <a_samp>`, `strcat((dest[0] = EOS, dest), src, sizeof dest)`, `format()` before `SendClientMessage` / `ShowPlayerDialog`, explicit all-8-parameter `SetVehicleParamsEx` calls, and untagged `OnPlayerStateChange` / `GetPlayerWeaponData` parameters.

## Reference Guides

Load only the reference matching the subsystem you are building or auditing:

| Subsystem | Guide | Covers |
|---|---|---|
| Accounts, auth & spawning | [references/accounts-and-characters.md](references/accounts-and-characters.md) | Multi-character SQL schema, `gRace` async guards, `samp-bcrypt`, staggered auto-save vs critical writes, `Streamer_UpdateEx` spawn state |
| Inventory & items | [references/inventory-and-items.md](references/inventory-and-items.md) | Normalized `character_items` table, static `E_ITEM_META` catalog, slot/weight/stack checks, duplication-proof `Inventory_Transfer`, Streamer ground drops |
| Vehicles & properties | [references/vehicles-and-properties.md](references/vehicles-and-properties.md) | Persistent `db_id` vs runtime `vehicleid`, `GetVehicleParamsEx`/`SetVehicleParamsEx`, trunks, `OnVehicleDeath` recovery, house/biz areas & VW isolation |
| Factions, economy & chat | [references/factions-economy-chat.md](references/factions-economy-chat.md) | Faction ranks & duty loadout save/restore, overflow-safe `Money_Transfer`, `VectorSize` proximity + 2-line 144-char wrapping |
