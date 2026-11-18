// Mirrors skills/pawn-anticheat/references/server-authoritative-state.md & movement-and-combat.md.
// Needs: omp-stdlib.
#include <open.mp>

const MAX_SAFE_CASH = 1_000_000_000;
const AC_GRACE_MS   = 1500;

static sPlayerCash[MAX_PLAYERS];
static sCashGraceUntil[MAX_PLAYERS];
static WEAPON:sPlayerWeapons[MAX_PLAYERS][13];
static sPlayerAmmo[MAX_PLAYERS][13];
static sWeaponGraceUntil[MAX_PLAYERS];
static sLastVehModel[MAX_PLAYERS];
static sLastShotTick[MAX_PLAYERS];
static sRapidFireStrikes[MAX_PLAYERS];
static sKickTimer[MAX_PLAYERS] = { -1, ... };

main() {}

static stock bool:AC_InGrace(untilTick)
{
	if (untilTick == 0) return false;
	return (GetTickCount() - untilTick) < 0;
}

static stock AC_GraceUntil(ms)
{
	new until = GetTickCount() + ms;
	if (until == 0) until = 1;
	return until;
}

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

static stock AC_ResetState(playerid)
{
	sPlayerCash[playerid] = 0;
	sCashGraceUntil[playerid] = 0;
	sWeaponGraceUntil[playerid] = 0;
	sLastVehModel[playerid] = 0;
	sLastShotTick[playerid] = 0;
	sRapidFireStrikes[playerid] = 0;
	for (new s = 0; s < 13; s++)
	{
		sPlayerWeapons[playerid][s] = WEAPON_FIST;
		sPlayerAmmo[playerid][s] = 0;
	}
	return 1;
}

public OnGameModeInit()
{
	EnableStuntBonusForAll(false);
	return 1;
}

public OnPlayerConnect(playerid)
{
	AC_ResetState(playerid);
	return 1;
}

public OnPlayerDisconnect(playerid, reason)
{
	if (sKickTimer[playerid] != -1)
	{
		KillTimer(sKickTimer[playerid]);
		sKickTimer[playerid] = -1;
	}
	AC_ResetState(playerid);
	return 1;
}

stock AC_SyncCash(playerid)
{
	sCashGraceUntil[playerid] = AC_GraceUntil(AC_GRACE_MS);
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

stock bool:AC_AuditCash(playerid)
{
	if (AC_InGrace(sCashGraceUntil[playerid])) return true;

	new clientCash = GetPlayerMoney(playerid);
	if (clientCash > sPlayerCash[playerid])
	{
		AC_SyncCash(playerid);
		AC_ScheduleKick(playerid, "Money mismatch");
		return false;
	}
	if (clientCash < sPlayerCash[playerid])
	{
		AC_SyncCash(playerid);
	}
	return true;
}

stock bool:AC_IsGivableWeapon(WEAPON:weaponid)
{
	new wid = _:weaponid;
	if (wid < 0 || wid > 46) return false;
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

	sWeaponGraceUntil[playerid] = AC_GraceUntil(AC_GRACE_MS);
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
	sWeaponGraceUntil[playerid] = AC_GraceUntil(AC_GRACE_MS);
	ResetPlayerWeapons(playerid);
	return 1;
}

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
		sWeaponGraceUntil[playerid] = AC_GraceUntil(AC_GRACE_MS);
	}
	else if (oldstate == PLAYER_STATE_DRIVER || oldstate == PLAYER_STATE_PASSENGER)
	{
		sWeaponGraceUntil[playerid] = AC_GraceUntil(AC_GRACE_MS);
	}
	return 1;
}

stock bool:AC_AuditWeapons(playerid)
{
	if (AC_InGrace(sWeaponGraceUntil[playerid])) return true;

	for (new slot = 0; slot < 13; slot++)
	{
		new WEAPON:clientWep, clientAmmo;
		GetPlayerWeaponData(playerid, WEAPON_SLOT:slot, clientWep, clientAmmo);
		if (clientWep == WEAPON_FIST || clientAmmo <= 0) continue;
		if (AC_IsVehicleEntryWeapon(playerid, clientWep)) continue;

		if (clientWep != sPlayerWeapons[playerid][slot] || clientAmmo > sPlayerAmmo[playerid][slot])
		{
			AC_ResetWeapons(playerid);
			AC_ScheduleKick(playerid, "Unauthorized weapon");
			return false;
		}
	}
	return true;
}

static stock AC_WeaponMinShotMs(WEAPON:weaponid)
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
	if (fX != fX || fY != fY || fZ != fZ
		|| floatabs(fX) > 20000.0 || floatabs(fY) > 20000.0 || floatabs(fZ) > 20000.0)
		return 0;

	new wid = _:weaponid;
	if (wid < 22 || wid > 38) return 0;

	new slot = _:GetWeaponSlot(weaponid);
	if (slot < 0 || slot >= 13
		|| (sPlayerWeapons[playerid][slot] != weaponid && !AC_IsVehicleEntryWeapon(playerid, weaponid)))
		return 0;

	if (hittype == BULLET_HIT_TYPE_PLAYER)
	{
		if (hitid == INVALID_PLAYER_ID || !IsPlayerConnected(hitid) || hitid == playerid)
			return 0;
		if (VectorSize(fX, fY, fZ) > 3.5)
			return 0;
	}

	new Float:ox, Float:oy, Float:oz, Float:hx, Float:hy, Float:hz;
	new Float:px, Float:py, Float:pz;
	GetPlayerLastShotVectors(playerid, ox, oy, oz, hx, hy, hz);
	GetPlayerPos(playerid, px, py, pz);
	if (VectorSize(ox - px, oy - py, oz - pz) > 12.0) return 0;
	if (VectorSize(hx - ox, hy - oy, hz - oz) > 350.0) return 0;

	new now = GetTickCount();
	new prev = sLastShotTick[playerid];
	sLastShotTick[playerid] = now;
	if (prev != 0 && (now - prev) >= 0 && (now - prev) < AC_WeaponMinShotMs(weaponid))
	{
		if (++sRapidFireStrikes[playerid] >= 3) return 0;
	}
	else if (sRapidFireStrikes[playerid] > 0)
	{
		sRapidFireStrikes[playerid]--;
	}
	return 1;
}

public OnPlayerGiveDamage(playerid, damagedid, Float:amount, WEAPON:weaponid, bodypart)
{
	if (damagedid == INVALID_PLAYER_ID || !IsPlayerConnected(damagedid) || damagedid == playerid)
		return 0;

	new wid = _:weaponid;
	if (wid < 0 || wid >= 47) return 0;

	if (amount != amount || amount <= 0.0 || amount > 150.0)
		return 0;

	if (22 <= wid <= 38)
	{
		new slot = _:GetWeaponSlot(weaponid);
		if (slot < 0 || slot >= 13
			|| (sPlayerWeapons[playerid][slot] != weaponid && !AC_IsVehicleEntryWeapon(playerid, weaponid)))
			return 0;
	}
	return 1;
}
