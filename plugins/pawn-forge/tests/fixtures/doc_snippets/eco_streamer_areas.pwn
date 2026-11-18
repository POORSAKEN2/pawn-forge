// Mirrors skills/pawn-ecosystem/references/streamer-and-world.md.
// Needs: omp-stdlib, samp-streamer-plugin.
#include <open.mp>
#include <streamer>

static const Float:sSafeZonePoly[] = {
	1450.0, -1750.0,
	1520.0, -1750.0,
	1520.0, -1680.0,
	1450.0, -1680.0
};

static STREAMER_TAG_AREA:sSafeZoneArea = STREAMER_TAG_AREA:0;
static STREAMER_TAG_AREA:sRadarCircle = STREAMER_TAG_AREA:0;
static STREAMER_TAG_AREA:sGarageSphere = STREAMER_TAG_AREA:0;
static STREAMER_TAG_AREA:sVaultCuboid = STREAMER_TAG_AREA:0;
static STREAMER_TAG_AREA:sPlayerBeacon[MAX_PLAYERS] = { STREAMER_TAG_AREA:0, ... };
static STREAMER_TAG_OBJECT:sPatrolSiren = STREAMER_TAG_OBJECT:0;
static sPatrolVeh = INVALID_VEHICLE_ID;

main() {}

public OnGameModeInit()
{
	Streamer_SetMaxItems(STREAMER_TYPE_OBJECT, 50000);
	Streamer_SetMaxItems(STREAMER_TYPE_AREA, 10000);
	Streamer_SetVisibleItems(STREAMER_TYPE_OBJECT, 700);
	Streamer_SetTickRate(50);
	Streamer_SetCellDistance(300.0);

	sSafeZoneArea = CreateDynamicPolygon(sSafeZonePoly, 0.0, 50.0, .worldid = 0, .interiorid = 0);
	sRadarCircle = CreateDynamicCircle(1200.0, -1400.0, 35.0, .worldid = 0);
	sGarageSphere = CreateDynamicSphere(1500.0, -1700.0, 13.5, 4.0, .worldid = 0, .interiorid = 0);
	sVaultCuboid = CreateDynamicCuboid(2140.0, 1605.0, 990.0, 2150.0, 1615.0, 1000.0, .worldid = 1, .interiorid = 1);

	sPatrolVeh = CreateVehicle(596, 1545.0, -1675.0, 13.5, 90.0, 0, 1, -1, false);
	if (sPatrolVeh != INVALID_VEHICLE_ID)
	{
		sPatrolSiren = CreateDynamicObject(18646, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0);
		AttachDynamicObjectToVehicle(sPatrolSiren, sPatrolVeh, -0.4, 0.1, 0.82, 0.0, 0.0, 0.0);
	}
	return 1;
}

public OnGameModeExit()
{
	if (IsValidDynamicObject(sPatrolSiren))
	{
		DestroyDynamicObject(sPatrolSiren);
		sPatrolSiren = STREAMER_TAG_OBJECT:0;
	}
	if (sPatrolVeh != INVALID_VEHICLE_ID)
	{
		DestroyVehicle(sPatrolVeh);
		sPatrolVeh = INVALID_VEHICLE_ID;
	}
	if (IsValidDynamicArea(sSafeZoneArea)) DestroyDynamicArea(sSafeZoneArea);
	if (IsValidDynamicArea(sRadarCircle)) DestroyDynamicArea(sRadarCircle);
	if (IsValidDynamicArea(sGarageSphere)) DestroyDynamicArea(sGarageSphere);
	if (IsValidDynamicArea(sVaultCuboid)) DestroyDynamicArea(sVaultCuboid);
	sSafeZoneArea = STREAMER_TAG_AREA:0;
	sRadarCircle = STREAMER_TAG_AREA:0;
	sGarageSphere = STREAMER_TAG_AREA:0;
	sVaultCuboid = STREAMER_TAG_AREA:0;
	return 1;
}

public OnPlayerConnect(playerid)
{
	sPlayerBeacon[playerid] = CreateDynamicSphere(0.0, 0.0, 0.0, 5.0, .playerid = -1);
	AttachDynamicAreaToPlayer(sPlayerBeacon[playerid], playerid);
	Streamer_SetIntData(STREAMER_TYPE_AREA, sPlayerBeacon[playerid], E_STREAMER_PLAYER_ID, -1);
	return 1;
}

public OnPlayerDisconnect(playerid, reason)
{
	if (IsValidDynamicArea(sPlayerBeacon[playerid]))
	{
		DestroyDynamicArea(sPlayerBeacon[playerid]);
		sPlayerBeacon[playerid] = STREAMER_TAG_AREA:0;
	}
	return 1;
}

public OnPlayerEnterDynamicArea(playerid, STREAMER_TAG_AREA:areaid)
{
	if (areaid == sSafeZoneArea)
		SendClientMessage(playerid, 0x2ECC71FF, "Entered safe zone.");
	else if (areaid == sGarageSphere)
		SendClientMessage(playerid, 0x3498DBFF, "Entered garage entrance.");
	else if (areaid == sRadarCircle)
		SendClientMessage(playerid, 0xF1C40FFF, "Speed camera zone ahead.");
	else if (areaid == sVaultCuboid)
		SendClientMessage(playerid, 0xE74C3CFF, "Entered restricted vault area.");
	return 1;
}

public OnPlayerLeaveDynamicArea(playerid, STREAMER_TAG_AREA:areaid)
{
	if (areaid == sSafeZoneArea)
		SendClientMessage(playerid, 0x95A5A6FF, "Left safe zone.");
	return 1;
}

stock bool:Eco_IsPlayerSafe(playerid)
{
	if (!IsPlayerConnected(playerid) || !IsValidDynamicArea(sSafeZoneArea))
		return false;
	return IsPlayerInDynamicArea(playerid, sSafeZoneArea) != 0;
}

stock Eco_GetBeaconOwner(STREAMER_TAG_AREA:areaid)
{
	if (!IsValidDynamicArea(areaid)) return INVALID_PLAYER_ID;
	return Streamer_GetIntData(STREAMER_TYPE_AREA, areaid, E_STREAMER_PLAYER_ID);
}

stock Eco_TeleportPreloaded(playerid, Float:x, Float:y, Float:z, worldid, interiorid)
{
	SetPlayerVirtualWorld(playerid, worldid);
	SetPlayerInterior(playerid, interiorid);
	Streamer_UpdateEx(playerid, x, y, z, worldid, interiorid);
	SetPlayerPos(playerid, x, y, z);
	return 1;
}
