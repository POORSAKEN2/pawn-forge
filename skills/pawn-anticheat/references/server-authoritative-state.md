# Server-Authoritative State (Cash, Weapons, Health & Armour)

Client memory in GTA:SA is trivially editable. Treat `GetPlayerMoney`, `GetPlayerWeaponData`, `GetPlayerHealth`, and `GetPlayerArmour` as **untrusted client claims** to audit against server shadow arrays—never as authoritative values.

## 1. Shadow Cash & Stunt Bonus Prevention

Disable GTA's client-side stunt cash payouts at startup, cap balances against 32-bit signed overflow (`MAX_SAFE_CASH = 1_000_000_000`), and mirror server balances to the HUD with `ResetPlayerMoney` + `GivePlayerMoney`.

```pawn
#include <open.mp> // on SA-MP 0.3.7: #include <a_samp>, EnableStuntBonusForAll(0)

const MAX_SAFE_CASH = 1_000_000_000;
const AC_GRACE_MS   = 1500;

static sPlayerCash[MAX_PLAYERS];
static sCashGraceUntil[MAX_PLAYERS];

stock bool:AC_InGrace(untilTick)
{
	// Signed subtraction stays valid across the 24.9-day GetTickCount() 32-bit wrap.
	return (GetTickCount() - untilTick) < 0;
}

public OnGameModeInit()
{
	EnableStuntBonusForAll(false);
	return 1;
}

stock AC_SyncCash(playerid)
{
	sCashGraceUntil[playerid] = GetTickCount() + AC_GRACE_MS;
	ResetPlayerMoney(playerid);
	GivePlayerMoney(playerid, sPlayerCash[playerid]);
	return 1;
}

stock bool:AC_GiveCash(playerid, delta)
{
	if (!IsPlayerConnected(playerid)) return false;
	if (delta > 0 && sPlayerCash[playerid] > MAX_SAFE_CASH - delta) return false;
	if (delta < 0 && sPlayerCash[playerid] + delta < 0) return false;

	sPlayerCash[playerid] += delta;
	AC_SyncCash(playerid);
	return true;
}

stock AC_GetCash(playerid)
{
	return (0 <= playerid < MAX_PLAYERS) ? sPlayerCash[playerid] : 0;
}

stock bool:AC_AuditCash(playerid)
{
	if (AC_InGrace(sCashGraceUntil[playerid])) return true;

	new clientCash = GetPlayerMoney(playerid);
	if (clientCash > sPlayerCash[playerid])
	{
		// Client injected cash (stunt bonuses are disabled, so upward drift is illegitimate).
		AC_SyncCash(playerid);
		return false;
	}
	if (clientCash < sPlayerCash[playerid])
	{
		// Downward drift can come from vending machines/Pay'n'Spray; resync HUD.
		AC_SyncCash(playerid);
	}
	return true;
}
```

> **Tip:** To avoid even downward cash desyncs from GTA vending machines and Pay 'n' Spray shops, strip them on connect with `RemoveBuildingForPlayer` or lock player-owned cash in your roleplay database (`pawn-roleplay`).

## 2. Shadow Weapons, Ammo & `GetWeaponSlot`

Store weapons in `sPlayerWeapons[MAX_PLAYERS][13]` and `sPlayerAmmo[MAX_PLAYERS][13]`, and wrap `GivePlayerWeapon` and `ResetPlayerWeapons` so every change sets `sWeaponGraceUntil[playerid]`.

### open.mp vs SA-MP 0.3.7 Slot Resolution

- **open.mp**: `native WEAPON_SLOT:GetWeaponSlot(WEAPON:weaponid)` is built into `<open.mp>` (`omp_core.inc`), and `GetPlayerWeaponData` expects `WEAPON_SLOT:slot` and `&WEAPON:weapon`.
- **SA-MP 0.3.7**: `GetWeaponSlot` is **not** in `<a_samp>`; include a `stock AC_GetWeaponSlot(weaponid)` helper:

```pawn
// SA-MP 0.3.7 helper (on open.mp use built-in GetWeaponSlot(WEAPON:weaponid))
stock AC_GetWeaponSlot(weaponid)
{
	switch (weaponid)
	{
		case 0, 1: return 0;
		case 2..9: return 1;
		case 22..24: return 2;
		case 25..27: return 3;
		case 28, 29, 32: return 4;
		case 30, 31: return 5;
		case 33, 34: return 6;
		case 35..38: return 7;
		case 16..18, 39: return 8;
		case 41..43: return 9;
		case 10..15: return 10;
		case 44..46: return 11;
		case 40: return 12;
	}
	return -1;
}
```

### Authoritative Weapon Wrappers

```pawn
static WEAPON:sPlayerWeapons[MAX_PLAYERS][13];
static sPlayerAmmo[MAX_PLAYERS][13];
static sWeaponGraceUntil[MAX_PLAYERS];

stock bool:AC_IsGivableWeapon(WEAPON:weaponid)
{
	new wid = _:weaponid;
	if (wid < 0 || wid > 46) return false;
	// 19, 20, 21 are unused/invalid GTA weapon slots.
	if (19 <= wid <= 21) return false;
	return true;
}

stock bool:AC_GiveWeapon(playerid, WEAPON:weaponid, ammo)
{
	if (!IsPlayerConnected(playerid) || ammo <= 0 || !AC_IsGivableWeapon(weaponid))
		return false;

	new slot = _:GetWeaponSlot(weaponid);
	if (slot < 0 || slot >= 13) return false;

	if (sPlayerWeapons[playerid][slot] == weaponid)
		sPlayerAmmo[playerid][slot] += ammo;
	else
	{
		sPlayerWeapons[playerid][slot] = weaponid;
		sPlayerAmmo[playerid][slot] = ammo;
	}

	sWeaponGraceUntil[playerid] = GetTickCount() + AC_GRACE_MS;
	GivePlayerWeapon(playerid, weaponid, ammo);
	return true;
}

stock AC_ResetWeapons(playerid)
{
	for (new s = 0; s < 13; s++)
	{
		sPlayerWeapons[playerid][s] = WEAPON_FIST;
		sPlayerAmmo[playerid][s] = 0;
	}
	sWeaponGraceUntil[playerid] = GetTickCount() + AC_GRACE_MS;
	ResetPlayerWeapons(playerid);
	return 1;
}
```

## 3. Vehicle-Entry Weapon Exceptions

GTA:SA automatically grants weapons on vehicle entry—even without server calls. Track `sLastVehModel[playerid]` in `OnPlayerStateChange` so entering or bailing out of these vehicles does not trigger false bans:

| Vehicle Model(s) | Auto-Granted Weapon | Slot | Notes |
|---|---|---|---|
| `596` (LSPD), `597` (SFPD), `598` (LVPD), `599` (Ranger) | `WEAPON_SHOTGUN` (`25`, 5 shells) | `3` | Granted on entry unless stripped on exit/state change |
| `457` (Caddy) | `WEAPON_GOLFCLUB` (`2`) | `1` | Granted on entry |
| `417, 425, 447, 460, 469, 476, 487, 488, 497, 511, 512, 513, 519, 520, 548, 553, 563, 577, 592, 593` | `WEAPON_PARACHUTE` (`46`) | `11` | Helicopters & airplanes grant parachute on entry |

```pawn
static sLastVehModel[MAX_PLAYERS];

stock bool:AC_IsAircraftModel(model)
{
	switch (model)
	{
		case 417, 425, 447, 460, 469, 476, 487, 488, 497,
		     511, 512, 513, 519, 520, 548, 553, 563, 577, 592, 593:
			return true;
	}
	return false;
}

stock bool:AC_IsVehicleEntryWeapon(playerid, WEAPON:weaponid)
{
	new model = sLastVehModel[playerid];
	new curVeh = GetPlayerVehicleID(playerid);
	if (curVeh != 0) model = GetVehicleModel(curVeh);

	if (weaponid == WEAPON_SHOTGUN && (596 <= model <= 599)) return true;
	if (weaponid == WEAPON_GOLFCLUB && model == 457) return true;
	if (weaponid == WEAPON_PARACHUTE && AC_IsAircraftModel(model)) return true;
	return false;
}

public OnPlayerStateChange(playerid, PLAYER_STATE:newstate, PLAYER_STATE:oldstate)
{
	if (newstate == PLAYER_STATE_DRIVER || newstate == PLAYER_STATE_PASSENGER)
	{
		new vid = GetPlayerVehicleID(playerid);
		if (vid != 0) sLastVehModel[playerid] = GetVehicleModel(vid);
		sWeaponGraceUntil[playerid] = GetTickCount() + AC_GRACE_MS;
	}
	else if (oldstate == PLAYER_STATE_DRIVER || oldstate == PLAYER_STATE_PASSENGER)
	{
		// Keep sLastVehModel until next vehicle entry or strip auto-granted weapons cleanly.
		sWeaponGraceUntil[playerid] = GetTickCount() + AC_GRACE_MS;
	}
	return 1;
}
```

### Weapon Audit Loop Caveats

1. **Skip `WEAPON_FIST` (`0`) and `clientAmmo == 0`:** Empty slots and spent throwables (`WEAPON_GRENADE`, `WEAPON_MOLTOV`, `WEAPON_SATCHEL`) often report `ammo == 0` in `GetPlayerWeaponData` before the client clears the slot.
2. **Track ammo downward only on confirmed shots or keep a tolerance:** Due to packet loss, client `GetPlayerWeaponData` ammo lags behind `OnPlayerWeaponShot`. Flag **upward** ammo jumps (`clientAmmo > sPlayerAmmo[playerid][slot]`) outside `sWeaponGraceUntil`, not small downward differences.
3. **Never run heavy per-slot audits in `OnPlayerUpdate` (`PF504`):** Audit weapons and cash on a 1000 ms repeating timer (or YSI `ptask AC_Sweep[1000](playerid)`), and always reset all shadow arrays in both `OnPlayerConnect` and `OnPlayerDisconnect`.

## 4. Server-Side Health & Armour Model

GTA handles fall damage, fire, explosions, Ambulances (`416`, +20 HP on entry), Enforcers (`427`, +100 armour on entry), and vending machines client-side unless intercepted.

- **Pure server-side combat damage (recommended for competitive/TDM/RP):**
  1. Put every player on the same team (`SetPlayerTeam(playerid, 1)`) so GTA does not deduct health on client-side gunfire (note: `SetPlayerTeam` disables client-side weapon/melee friendly damage, while fall/fire/vehicle damage still occurs).
  2. Maintain `Float:sPlayerHealth[MAX_PLAYERS]` and `Float:sPlayerArmour[MAX_PLAYERS]`, wrapping every heal/vest via `AC_SetPlayerHealth` / `AC_SetPlayerArmour` with `sHealthGraceUntil[playerid]`.
  3. Deduct damage inside `OnPlayerTakeDamage` (after NaN/range/weapon validation) from `sPlayerArmour` first, then `sPlayerHealth`, and call `SetPlayerArmour` / `SetPlayerHealth` immediately.
- **Hybrid audit (if keeping default GTA damage):**
  - Only flag **unexpected increases** (`clientHP > sPlayerHealth[playerid] + 1.0`) outside `sHealthGraceUntil` and outside Ambulance (`416`) / Enforcer (`427`) / vending machine interactions. Never ban for slow client health *decreases*—lagging players look "god-moded" briefly until hit sync catches up.
