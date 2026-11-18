// Mirrors skills/pawn-anticheat/references/movement-and-combat.md.
// Needs: omp-stdlib.
#include <open.mp>

#if !defined isnull
	#define isnull(%1) ((!(%1[0])) || (((%1[0]) == '\1') && (!(%1[1]))))
#endif

const AC_TP_GRACE_MS   = 2500;
const MAX_PIN_ATTEMPTS = 3;

enum {
	DIALOG_NONE = 0,
	DIALOG_ADMIN_PIN,
	DIALOG_ACTION_MENU
}

static sActiveDialog[MAX_PLAYERS] = { DIALOG_NONE, ... };
static sDialogMaxItems[MAX_PLAYERS];
static sPinAttempts[MAX_PLAYERS];
static sKickTimer[MAX_PLAYERS] = { -1, ... };
static sTeleportGraceUntil[MAX_PLAYERS];
static Float:sLastX[MAX_PLAYERS];
static Float:sLastY[MAX_PLAYERS];
static Float:sLastZ[MAX_PLAYERS];
static sLastMoveTick[MAX_PLAYERS];
static sSpeedStrikes[MAX_PLAYERS];

main() {}

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

static stock AC_ResetPlayer(playerid)
{
	sActiveDialog[playerid] = DIALOG_NONE;
	sDialogMaxItems[playerid] = 0;
	sPinAttempts[playerid] = 0;
	sTeleportGraceUntil[playerid] = 0;
	sLastX[playerid] = 0.0;
	sLastY[playerid] = 0.0;
	sLastZ[playerid] = 0.0;
	sLastMoveTick[playerid] = GetTickCount();
	sSpeedStrikes[playerid] = 0;
	return 1;
}

public OnPlayerConnect(playerid)
{
	AC_ResetPlayer(playerid);
	return 1;
}

public OnPlayerDisconnect(playerid, reason)
{
	if (sKickTimer[playerid] != -1)
	{
		KillTimer(sKickTimer[playerid]);
		sKickTimer[playerid] = -1;
	}
	AC_ResetPlayer(playerid);
	return 1;
}

stock bool:AC_ShowDialog(playerid, dialogid, DIALOG_STYLE:style, const title[], const body[], const b1[], const b2[], maxItems = 0)
{
	if (!IsPlayerConnected(playerid) || dialogid == DIALOG_NONE) return false;
	sActiveDialog[playerid] = dialogid;
	sDialogMaxItems[playerid] = maxItems;
	return ShowPlayerDialog(playerid, dialogid, style, title, body, b1, b2);
}

stock bool:AC_SetPlayerPos(playerid, Float:x, Float:y, Float:z)
{
	sLastX[playerid] = x;
	sLastY[playerid] = y;
	sLastZ[playerid] = z;
	sLastMoveTick[playerid] = GetTickCount();
	sTeleportGraceUntil[playerid] = GetTickCount() + AC_TP_GRACE_MS;
	sSpeedStrikes[playerid] = 0;
	return SetPlayerPos(playerid, x, y, z);
}

stock bool:AC_CheckMovement(playerid)
{
	if (!IsPlayerConnected(playerid)) return true;

	new now = GetTickCount();
	if ((now - sTeleportGraceUntil[playerid]) < 0)
		return true;

	new PLAYER_STATE:state = GetPlayerState(playerid);
	if (state != PLAYER_STATE_ONFOOT && state != PLAYER_STATE_DRIVER)
		return true;

	if (GetPlayerSurfingVehicleID(playerid) != INVALID_VEHICLE_ID)
		return true;

	new Float:x, Float:y, Float:z;
	GetPlayerPos(playerid, x, y, z);

	new dt = now - sLastMoveTick[playerid];
	if (dt < 250) return true;
	if (dt > 5000)
	{
		sLastX[playerid] = x; sLastY[playerid] = y; sLastZ[playerid] = z;
		sLastMoveTick[playerid] = now;
		return true;
	}

	new Float:horizDist = VectorSize(x - sLastX[playerid], y - sLastY[playerid], 0.0);
	new Float:dz = z - sLastZ[playerid];
	new bool:falling = (dz < -4.0)
		|| (GetPlayerWeapon(playerid) == WEAPON_PARACHUTE)
		|| (1128 <= GetPlayerAnimationIndex(playerid) <= 1134);

	new Float:vx, Float:vy, Float:vz;
	if (state == PLAYER_STATE_DRIVER)
		GetVehicleVelocity(GetPlayerVehicleID(playerid), vx, vy, vz);
	else
		GetPlayerVelocity(playerid, vx, vy, vz);

	new Float:speedMps = horizDist / (float(dt) / 1000.0);
	new Float:maxMps = (state == PLAYER_STATE_DRIVER) ? 95.0 : 22.0;

	sLastX[playerid] = x; sLastY[playerid] = y; sLastZ[playerid] = z;
	sLastMoveTick[playerid] = now;

	if (!falling && (speedMps > maxMps || VectorSize(vx, vy, vz) > 2.5))
	{
		if (++sSpeedStrikes[playerid] >= 3)
		{
			AC_ScheduleKick(playerid, "Movement anomaly");
			return false;
		}
	}
	else if (sSpeedStrikes[playerid] > 0)
	{
		sSpeedStrikes[playerid]--;
	}
	return true;
}

stock AC_PromptAdminPin(playerid)
{
	return AC_ShowDialog(playerid, DIALOG_ADMIN_PIN, DIALOG_STYLE_PASSWORD,
		"Admin Verification", "Enter your 4-digit staff PIN:", "Submit", "Cancel");
}

public OnDialogResponse(playerid, dialogid, response, listitem, inputtext[])
{
	if (dialogid == DIALOG_NONE || dialogid != sActiveDialog[playerid])
	{
		AC_ScheduleKick(playerid, "Invalid dialog response");
		return 1;
	}

	new maxItems = sDialogMaxItems[playerid];
	sActiveDialog[playerid] = DIALOG_NONE;
	sDialogMaxItems[playerid] = 0;

	if (!response) return 1;

	switch (dialogid)
	{
		case DIALOG_ADMIN_PIN:
		{
			if (isnull(inputtext) || strlen(inputtext) > 16)
			{
				SendClientMessage(playerid, 0xFF4444FF, "Enter a valid PIN.");
				AC_PromptAdminPin(playerid);
				return 1;
			}
			if (strcmp(inputtext, "8492") != 0)
			{
				if (++sPinAttempts[playerid] >= MAX_PIN_ATTEMPTS)
				{
					AC_ScheduleKick(playerid, "Too many failed PIN attempts");
					return 1;
				}
				SendClientMessage(playerid, 0xFF4444FF, "Incorrect PIN.");
				AC_PromptAdminPin(playerid);
				return 1;
			}
			sPinAttempts[playerid] = 0;
			AC_ShowDialog(playerid, DIALOG_ACTION_MENU, DIALOG_STYLE_LIST,
				"Staff Teleport", "LS Spawn\nSF Spawn\nLV Spawn", "Select", "Close", 3);
			return 1;
		}
		case DIALOG_ACTION_MENU:
		{
			if (listitem < 0 || listitem >= maxItems)
			{
				AC_ScheduleKick(playerid, "Dialog listitem out of bounds");
				return 1;
			}
			switch (listitem)
			{
				case 0: AC_SetPlayerPos(playerid, 1742.9, -1860.6, 13.57);
				case 1: AC_SetPlayerPos(playerid, -1968.7, 138.0, 27.68);
				case 2: AC_SetPlayerPos(playerid, 2027.0, 1007.9, 10.82);
			}
			return 1;
		}
	}
	return 1;
}
