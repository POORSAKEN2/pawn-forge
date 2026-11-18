# Movement, Combat, Dialogs & Delayed Kick

Client movement, bullet vectors, damage reports, and dialog responses are network inputs—never ground truth. Validate bounds, finite floats, state exclusions, and server-side dialog ownership before mutating game state or indexing arrays.

## 1. Movement, Speed & Teleport Checks

Wrap `SetPlayerPos` (and `SetPlayerPosFindZ`, `PutPlayerInVehicle`) in `AC_SetPlayerPos` so legitimate server teleports update `sLastPos` and open a 2500 ms grace window. On mapped interiors/exteriors, call `Streamer_UpdateEx` before `SetPlayerPos` (`pawn-standards`).

```pawn
const AC_TP_GRACE_MS = 2500;

static Float:sLastX[MAX_PLAYERS];
static Float:sLastY[MAX_PLAYERS];
static Float:sLastZ[MAX_PLAYERS];
static sLastMoveTick[MAX_PLAYERS];
static sTeleportGraceUntil[MAX_PLAYERS];
static sSpeedStrikes[MAX_PLAYERS];

stock AC_SetPlayerPos(playerid, Float:x, Float:y, Float:z)
{
	sLastX[playerid] = x;
	sLastY[playerid] = y;
	sLastZ[playerid] = z;
	sLastMoveTick[playerid] = GetTickCount();
	sTeleportGraceUntil[playerid] = GetTickCount() + AC_TP_GRACE_MS;
	sSpeedStrikes[playerid] = 0;
	return SetPlayerPos(playerid, x, y, z);
}
```

### Lag-Tolerant Delta Check & Mandatory Exclusions

Check movement on a 500–1000 ms timer (not every frame in `OnPlayerUpdate`) and exclude passengers, surfers, falling players, and packet stalls:

```pawn
stock AC_CheckMovement(playerid)
{
	if (!IsPlayerConnected(playerid)) return 1;

	new now = GetTickCount();
	if ((now - sTeleportGraceUntil[playerid]) < 0)
		return 1; // Inside server-teleport grace window.

	new PLAYER_STATE:state = GetPlayerState(playerid);
	if (state != PLAYER_STATE_ONFOOT && state != PLAYER_STATE_DRIVER)
		return 1; // Exclude PASSENGER, SPECTATING, WASTED, NONE.

	if (GetPlayerSurfingVehicleID(playerid) != INVALID_VEHICLE_ID)
		return 1; // Vehicle surfers inherit the vehicle's velocity.

	new Float:x, Float:y, Float:z;
	GetPlayerPos(playerid, x, y, z);

	// Update baseline without flagging on long packet stalls (> 5 s) or tiny ticks (< 250 ms).
	new dt = now - sLastMoveTick[playerid];
	if (dt < 250) return 1;
	if (dt > 5000)
	{
		sLastX[playerid] = x; sLastY[playerid] = y; sLastZ[playerid] = z;
		sLastMoveTick[playerid] = now;
		return 1;
	}

	new Float:horizDist = VectorSize(x - sLastX[playerid], y - sLastY[playerid], 0.0);
	new Float:dz = z - sLastZ[playerid];

	// Exclude freefall, parachute diving, and GTA fall animations.
	new bool:falling = (dz < -4.0)
		|| (GetPlayerWeapon(playerid) == WEAPON_PARACHUTE)
		|| (1128 <= GetPlayerAnimationIndex(playerid) <= 1134);

	new Float:vx, Float:vy, Float:vz;
	if (state == PLAYER_STATE_DRIVER)
		GetVehicleVelocity(GetPlayerVehicleID(playerid), vx, vy, vz);
	else
		GetPlayerVelocity(playerid, vx, vy, vz);

	new Float:speedMps = horizDist / (float(dt) / 1000.0);
	new Float:maxMps = (state == PLAYER_STATE_DRIVER) ? 95.0 : 22.0; // ~342 km/h veh, ~79 km/h foot + lag buffer

	sLastX[playerid] = x; sLastY[playerid] = y; sLastZ[playerid] = z;
	sLastMoveTick[playerid] = now;

	if (!falling && (speedMps > maxMps || VectorSize(vx, vy, vz) > 2.5))
	{
		if (++sSpeedStrikes[playerid] >= 3)
			return 0; // Confirmed speed/teleport anomaly.
	}
	else if (sSpeedStrikes[playerid] > 0)
	{
		sSpeedStrikes[playerid]--;
	}
	return 1;
}
```

> **Jetpack check:** If your gamemode never awards jetpacks, check `GetPlayerSpecialAction(playerid) == SPECIAL_ACTION_USEJETPACK` (SA-MP 0.3.7: untagged `GetPlayerSpecialAction`).

## 2. Combat Callbacks (`OnPlayerWeaponShot`, Damage & Death)

Verify platform signatures before implementing:
- **open.mp**:
  - `public OnPlayerWeaponShot(playerid, WEAPON:weaponid, BULLET_HIT_TYPE:hittype, hitid, Float:fX, Float:fY, Float:fZ)`
  - `public OnPlayerGiveDamage(playerid, damagedid, Float:amount, WEAPON:weaponid, bodypart)`
  - `public OnPlayerTakeDamage(playerid, issuerid, Float:amount, WEAPON:weaponid, bodypart)`
  - `public OnPlayerDeath(playerid, killerid, WEAPON:reason)`
- **SA-MP 0.3.7**: identical parameter order, but `weaponid`, `hittype`, and `reason` are untagged `int`.

### `OnPlayerWeaponShot`: NaN, Bounds (`PF703`), Distance & Rapid-Fire

```pawn
static sLastShotTick[MAX_PLAYERS];
static sRapidFireStrikes[MAX_PLAYERS];
static sLastDamager[MAX_PLAYERS] = { INVALID_PLAYER_ID, ... };
static sLastDamageTick[MAX_PLAYERS];

stock AC_WeaponMinShotMs(WEAPON:weaponid)
{
	switch (weaponid)
	{
		case WEAPON_DEAGLE:   return 350;
		case WEAPON_SHOTGUN:  return 550;
		case WEAPON_RIFLE:    return 550;
		case WEAPON_SNIPER:   return 650;
		case WEAPON_COLT45, WEAPON_SILENCED: return 140;
		case WEAPON_UZI, WEAPON_TEC9, WEAPON_MP5, WEAPON_AK47, WEAPON_M4: return 45;
	}
	return 40;
}

public OnPlayerWeaponShot(playerid, WEAPON:weaponid, BULLET_HIT_TYPE:hittype, hitid, Float:fX, Float:fY, Float:fZ)
{
	// 1. Reject NaN/Inf/absurd coordinates (in Pawn, NaN != NaN evaluates true).
	if (fX != fX || fY != fY || fZ != fZ
		|| floatabs(fX) > 20000.0 || floatabs(fY) > 20000.0 || floatabs(fZ) > 20000.0)
		return 0;

	// 2. Bounds-check weaponid before any table/array access (PF703).
	new wid = _:weaponid;
	if (wid < 22 || wid > 38) return 0; // Non-bullet weapon IDs cannot fire bullets.

	// 3. Validate hitid for player hits before indexing player arrays (PF703).
	if (hittype == BULLET_HIT_TYPE_PLAYER)
	{
		if (hitid == INVALID_PLAYER_ID || !IsPlayerConnected(hitid) || hitid == playerid)
			return 0;

		// For BULLET_HIT_TYPE_PLAYER, fX/fY/fZ are local offsets from the target's center.
		if (VectorSize(fX, fY, fZ) > 3.5)
			return 0; // Silent-aim / spoofed hit offset.
	}

	// 4. Verify shot origin matches server position & check bullet distance.
	new Float:ox, Float:oy, Float:oz, Float:hx, Float:hy, Float:hz;
	new Float:px, Float:py, Float:pz;
	GetPlayerLastShotVectors(playerid, ox, oy, oz, hx, hy, hz);
	GetPlayerPos(playerid, px, py, pz);
	if (VectorSize(ox - px, oy - py, oz - pz) > 12.0)
		return 0; // Spoofed shot origin.

	if (VectorSize(hx - ox, hy - oy, hz - oz) > 350.0)
		return 0; // Beyond max GTA render/weapon range.

	// 5. Lag-tolerant rapid-fire check (burst packets can condense two shots; require 3 strikes).
	new now = GetTickCount();
	new dt = now - sLastShotTick[playerid];
	sLastShotTick[playerid] = now;
	if (dt >= 0 && dt < AC_WeaponMinShotMs(weaponid))
	{
		if (++sRapidFireStrikes[playerid] >= 3)
			return 0;
	}
	else if (sRapidFireStrikes[playerid] > 0)
	{
		sRapidFireStrikes[playerid]--;
	}
	return 1;
}
```

### Cross-Checking `OnPlayerGiveDamage` & `OnPlayerDeath`

```pawn
public OnPlayerGiveDamage(playerid, damagedid, Float:amount, WEAPON:weaponid, bodypart)
{
	// Bounds-check damagedid and weaponid first (PF703).
	if (damagedid == INVALID_PLAYER_ID || !IsPlayerConnected(damagedid) || damagedid == playerid)
		return 0;

	new wid = _:weaponid;
	if (wid < 0 || wid >= 47) return 0;

	if (amount != amount || amount <= 0.0 || amount > 150.0)
		return 0; // NaN or impossible single-hit weapon damage.

	if (GetPlayerVirtualWorld(playerid) != GetPlayerVirtualWorld(damagedid))
		return 0;

	sLastDamager[damagedid] = playerid;
	sLastDamageTick[damagedid] = GetTickCount();
	return 1;
}

public OnPlayerDeath(playerid, killerid, WEAPON:reason)
{
	if (killerid != INVALID_PLAYER_ID)
	{
		if (!IsPlayerConnected(killerid) || killerid == playerid)
			return 0;

		// Guard against fake-kill scripts when no recent damage came from killerid.
		if (sLastDamager[playerid] != killerid || (GetTickCount() - sLastDamageTick[playerid]) > 10000)
		{
			// Log/flag suspected fake-kill; avoid crediting killer score/bounty.
			return 1;
		}
	}
	sLastDamager[playerid] = INVALID_PLAYER_ID;
	return 1;
}
```

## 3. Dialog Spoofing, `PF702` Empty-`strcmp`, `PF704` RCON & `PF701` Delayed Kick

Clients can forge `OnDialogResponse` for any `dialogid` at any time, send empty strings to bypass `strcmp`, and exploit unescaped `%s` in `SendRconCommand`.

1. **Track `sActiveDialog[playerid]`** (using an `enum`, never magic numbers `PF505`) and clear it on entry to `OnDialogResponse`.
2. **Guard `strcmp` against empty `inputtext` (`PF702`):** In Pawn, `strcmp("secret", "")` returns `0`! Always check `if (isnull(inputtext))` (or `if (!inputtext[0])`) before `strcmp`. If not using `YSI` or `sscanf2`, define:
   `#if !defined isnull`
   `#define isnull(%1) ((!(%1[0])) || (((%1[0]) == '\1') && (!(%1[1]))))`
   `#endif`
3. **Never pass `%s` into `SendRconCommand` (`PF704`):** Format only numeric `%d` or static commands, or execute the action directly via Pawn natives.
4. **Always delay `Kick`/`Ban` (`PF701`):** Calling `Kick(playerid)` immediately after `SendClientMessage`/`ShowPlayerDialog` drops the outgoing message packet. Use `SetTimerEx` (250 ms) or YSI `defer`, store the timer ID so `KillTimer` cancels it in `OnPlayerDisconnect` (`PF402`), and guard against duplicate timers.

```pawn
enum {
	DIALOG_NONE = 0,
	DIALOG_ADMIN_PIN,
	DIALOG_ACTION_MENU
}

static sActiveDialog[MAX_PLAYERS] = { DIALOG_NONE, ... };
static sDialogMaxItems[MAX_PLAYERS];
static sKickTimer[MAX_PLAYERS] = { -1, ... };

forward AC_ExecKick(playerid);
public AC_ExecKick(playerid)
{
	sKickTimer[playerid] = -1;
	if (IsPlayerConnected(playerid)) Kick(playerid);
	return 1;
}

stock AC_ScheduleKick(playerid, const reason[])
{
	if (!IsPlayerConnected(playerid) || sKickTimer[playerid] != -1) return 0;
	SendClientMessage(playerid, 0xFF4444FF, "Disconnected: %s", reason);
	sKickTimer[playerid] = SetTimerEx("AC_ExecKick", 250, false, "d", playerid);
	return 1;
}

stock AC_ShowDialog(playerid, dialogid, DIALOG_STYLE:style, const title[], const body[], const b1[], const b2[], maxItems = 0)
{
	sActiveDialog[playerid] = dialogid;
	sDialogMaxItems[playerid] = maxItems;
	return ShowPlayerDialog(playerid, dialogid, style, title, body, b1, b2);
}
```
