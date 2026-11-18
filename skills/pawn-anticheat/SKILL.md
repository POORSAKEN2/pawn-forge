---
name: pawn-anticheat
description: Server-authoritative anti-cheat and security hardening for SA-MP 0.3.7 and open.mp Pawn servers, covering shadow cash/weapons/health, vehicle-entry weapon exceptions, GetTickCount() movement and teleport grace windows, NaN/distance/rapid-fire combat checks, dialog and RCON exploit guards, delayed Kick/Ban, Pawn.RakNet BitStream validation, and Nex-AC integration. Use when building, hardening, or auditing anti-cheat, combat, movement, dialog, or RakNet packet/RPC validation in Pawn.
license: MIT
compatibility: Optional Python 3.8+ for pawnforge CLI / MCP verification and pawncc 3.10.x compiler.
metadata:
  author: POORSAKEN2
  version: "0.2.0"
---

# Anti-Cheat & Security in Modern Pawn

Assume every client-reported value is spoofable. Enforce server-authoritative memory, lag-tolerant grace windows, strict bounds checks, and delayed disconnects. Follow `pawn-standards` for baseline Pawn safety, `pawn-roleplay` for economy/inventory integrity, `pawn-ecosystem` for RakNet/plugin patterns, and `pawn-audit` for codebase security reviews.

## Tool Resolution Order

Use the first available tier for verification:
1. **Pawn Forge MCP** (if connected): `project_info`, `compile`, `lint`, `api_lookup`, `lookup`.
2. **Standalone CLI**: `pawnforge <cmd> --json` (or `python scripts/pawnforge_exec.py <cmd> --json`, `python -m pawnforge <cmd> --json`, or `uvx --from git+https://github.com/POORSAKEN2/pawn-forge pawnforge <cmd> --json`).
3. **Fallback**: inspect local `.inc` signatures, compile with `pawncc`, and suggest `pip install git+https://github.com/POORSAKEN2/pawn-forge.git`.

Verify every callback/native signature (`api_lookup` / `pawnforge api`) and weapon/vehicle ID (`lookup` / `pawnforge lookup`) before writing code.

## Non-Negotiable Anti-Cheat Rules

1. **Never trust client state.** Track authoritative cash (`sPlayerCash`), weapons (`sPlayerWeapons[MAX_PLAYERS][13]`, `sPlayerAmmo[MAX_PLAYERS][13]`), health/armour (`sPlayerHealth`, `sPlayerArmour`), and active dialog (`sActiveDialog`) in server memory. Never treat `GetPlayerMoney`, `GetPlayerWeaponData`, `GetPlayerHealth`, `dialogid`, or client damage/position packets as ground truth.
2. **Close built-in client grants and whitelist GTA vehicle weapons.** Call `EnableStuntBonusForAll(false)` in `OnGameModeInit`. Whitelist GTA's automatic vehicle-entry weapons: Shotgun (`WEAPON_SHOTGUN`) in Police cars (`596`–`599`), Golf Club (`WEAPON_GOLFCLUB`) in Caddy (`457`), and Parachute (`WEAPON_PARACHUTE`) in aircraft.
3. **Use `GetTickCount()` grace windows, never zero-tolerance deltas.** Every server mutation (`AC_GiveWeapon`, `AC_GiveCash`, `AC_SetPlayerPos`) sets a 1500–2500 ms grace window checked via wrap-safe `(GetTickCount() - until) < 0`. Exclude passengers, vehicle surfers (`GetPlayerSurfingVehicleID`), falling/parachuting, and require multi-strike confirmation for lag-sensitive checks.
4. **Bounds-check every combat, dialog, and RCON input.** Reject `NaN` floats (`fX != fX`), invalid `BULLET_HIT_TYPE` / `WEAPON:` indices / `INVALID_PLAYER_ID` targets before indexing arrays (`PF703`), unknown `dialogid` / out-of-range `listitem`, unguarded `strcmp` on empty `inputtext` (`PF702`), and `%s` formatting inside `SendRconCommand` (`PF704`).
5. **Delay `Kick`/`Ban` so warning packets flush.** Schedule disconnects via `SetTimerEx` (200–500 ms) or YSI `defer` after `SendClientMessage`/`ShowPlayerDialog` (`PF701`). Store repeating/pending timer IDs and `KillTimer` on disconnect (`PF402`).
6. **Filter malformed RakNet packets/RPCs and free `BitStream` handles.** Validate bit lengths, finite floats, seats, and RPC bounds in `Pawn.RakNet` (`OnIncomingPacket`/`OnIncomingRPC`), reset read pointers before returning `1`, and free every `BS_New`/`BS_NewCopy` with `BS_Delete` (`PF801`). Verify changes with `pawn-build` and `pawn-test`.

## SA-MP 0.3.7 vs open.mp

- **open.mp**: `#include <open.mp>`, tagged callbacks/natives (`WEAPON:weaponid`, `BULLET_HIT_TYPE:hittype`, `WEAPON_SLOT:slot`, `PLAYER_STATE:newstate`, `DIALOG_STYLE:style`, `bool:EnableStuntBonusForAll(bool:enable)`), and built-in `WEAPON_SLOT:GetWeaponSlot(WEAPON:weaponid)`.
- **SA-MP 0.3.7**: `#include <a_samp>`, untagged callback/native parameters, and no stdlib `GetWeaponSlot` (provide a `stock AC_GetWeaponSlot(weaponid)` helper).

## Reference Guides

Load only the reference matching the subsystem you are hardening:

| Subsystem | Guide | Covers |
|---|---|---|
| Authoritative state | [references/server-authoritative-state.md](references/server-authoritative-state.md) | Shadow cash/weapons/ammo/HP/armour, `sWeaponGraceUntil`, vehicle-entry weapon exceptions, `EnableStuntBonusForAll(false)`, SA-MP vs open.mp slot helper |
| Movement & combat | [references/movement-and-combat.md](references/movement-and-combat.md) | `GetTickCount()` speed/TP checks & exclusions, `OnPlayerWeaponShot` NaN/distance/rapid-fire, `OnPlayerGiveDamage`/`OnPlayerDeath` checks, `sActiveDialog`, `PF701`–`PF704` |
| RakNet & Nex-AC | [references/raknet-and-nexac.md](references/raknet-and-nexac.md) | `Pawn.RakNet` packets `207`/`200`/`211`/`206` & RPCs `62`/`115`/`106`, `BS_Delete` hygiene (`PF801`), `nex-ac` include order & `OnCheatDetected` |
