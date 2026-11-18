// Mirrors skills/pawn-roleplay/references/vehicles-and-properties.md.
// Needs: omp-stdlib, mysqlinc, samp-streamer-plugin, Pawn.CMD/src, sscanf.
#include <open.mp>
#include <a_mysql>
#include <streamer>
#include <Pawn.CMD>
#include <sscanf2>

#define MAX_SERVER_VEHICLES 100
#define MAX_HOUSES 100
#define VW_HOUSE_BASE 10000

enum E_SERVER_VEH {
	bool:E_VEH_ACTIVE,
	E_VEH_DB_ID,
	E_VEH_OWNER_CHAR_ID,
	E_VEH_MODEL,
	E_VEH_PLATE[16],
	E_VEH_RUNTIME_ID,
	Float:E_VEH_HEALTH,
	bool:E_VEH_LOCKED,
	bool:E_VEH_ENGINE,
	bool:E_VEH_BOOT,
	bool:E_VEH_DESTROYED
}

enum E_HOUSE_DATA {
	bool:E_HOUSE_ACTIVE,
	E_HOUSE_DB_ID,
	E_HOUSE_OWNER_CHAR_ID,
	bool:E_HOUSE_LOCKED,
	Float:E_HOUSE_EXT_X,
	Float:E_HOUSE_EXT_Y,
	Float:E_HOUSE_EXT_Z,
	Float:E_HOUSE_INT_X,
	Float:E_HOUSE_INT_Y,
	Float:E_HOUSE_INT_Z,
	E_HOUSE_INT_ID,
	STREAMER_TAG_PICKUP:E_HOUSE_PICKUP,
	STREAMER_TAG_3D_TEXT_LABEL:E_HOUSE_LABEL,
	STREAMER_TAG_AREA:E_HOUSE_AREA
}

new MySQL:gSQL;
static gServerVeh[MAX_SERVER_VEHICLES][E_SERVER_VEH];
static gVehByRuntime[MAX_VEHICLES] = { -1, ... };
static gHouses[MAX_HOUSES][E_HOUSE_DATA];
static gPlayerNearHouse[MAX_PLAYERS] = { -1, ... };
static gCharId[MAX_PLAYERS];

stock Veh_CreatePersistent(idx, dbId, ownerCharId, model, Float:x, Float:y, Float:z, Float:a, col1, col2, const plate[])
{
	if (idx < 0 || idx >= MAX_SERVER_VEHICLES) return INVALID_VEHICLE_ID;

	new vid = CreateVehicle(model, x, y, z, a, col1, col2, -1, false);
	if (vid == INVALID_VEHICLE_ID) return INVALID_VEHICLE_ID;

	gServerVeh[idx][E_VEH_ACTIVE] = true;
	gServerVeh[idx][E_VEH_DB_ID] = dbId;
	gServerVeh[idx][E_VEH_OWNER_CHAR_ID] = ownerCharId;
	gServerVeh[idx][E_VEH_MODEL] = model;
	gServerVeh[idx][E_VEH_RUNTIME_ID] = vid;
	gServerVeh[idx][E_VEH_HEALTH] = 1000.0;
	gServerVeh[idx][E_VEH_LOCKED] = true;
	gServerVeh[idx][E_VEH_ENGINE] = false;
	gServerVeh[idx][E_VEH_BOOT] = false;
	gServerVeh[idx][E_VEH_DESTROYED] = false;
	strcopy(gServerVeh[idx][E_VEH_PLATE], plate, 16);
	gVehByRuntime[vid] = idx;

	SetVehicleNumberPlate(vid, gServerVeh[idx][E_VEH_PLATE]);
	SetVehicleParamsEx(vid, 0, 0, 0, 1, 0, 0, 0);
	return vid;
}

stock Veh_DestroyPersistent(idx)
{
	if (idx < 0 || idx >= MAX_SERVER_VEHICLES || !gServerVeh[idx][E_VEH_ACTIVE]) return 0;

	new vid = gServerVeh[idx][E_VEH_RUNTIME_ID];
	if (vid != INVALID_VEHICLE_ID && IsValidVehicle(vid))
	{
		gVehByRuntime[vid] = -1;
		DestroyVehicle(vid);
	}
	gServerVeh[idx][E_VEH_RUNTIME_ID] = INVALID_VEHICLE_ID;
	gServerVeh[idx][E_VEH_ACTIVE] = false;
	return 1;
}

stock Veh_ToggleEngine(playerid, vehicleid)
{
	if (vehicleid <= 0 || vehicleid >= MAX_VEHICLES) return 0;
	new idx = gVehByRuntime[vehicleid];
	if (idx < 0 || idx >= MAX_SERVER_VEHICLES || !gServerVeh[idx][E_VEH_ACTIVE]) return 0;
	if (gServerVeh[idx][E_VEH_OWNER_CHAR_ID] != gCharId[playerid]) return 0;
	if (GetPlayerState(playerid) != PLAYER_STATE_DRIVER) return 0;

	new engine, lights, alarm, doors, bonnet, boot, objective;
	GetVehicleParamsEx(vehicleid, engine, lights, alarm, doors, bonnet, boot, objective);
	new nextEngine = (engine == 1) ? 0 : 1;
	gServerVeh[idx][E_VEH_ENGINE] = (nextEngine == 1);
	SetVehicleParamsEx(vehicleid, nextEngine, lights, alarm, doors, bonnet, boot, objective);
	return 1;
}

stock Veh_ToggleLock(playerid, idx)
{
	if (idx < 0 || idx >= MAX_SERVER_VEHICLES || !gServerVeh[idx][E_VEH_ACTIVE]) return 0;
	if (gServerVeh[idx][E_VEH_OWNER_CHAR_ID] != gCharId[playerid]) return 0;

	new vid = gServerVeh[idx][E_VEH_RUNTIME_ID];
	if (vid == INVALID_VEHICLE_ID || !IsValidVehicle(vid)) return 0;

	new Float:vx, Float:vy, Float:vz, Float:px, Float:py, Float:pz;
	GetVehiclePos(vid, vx, vy, vz);
	GetPlayerPos(playerid, px, py, pz);
	if (VectorSize(vx - px, vy - py, vz - pz) > 4.5) return 0;

	new engine, lights, alarm, doors, bonnet, boot, objective;
	GetVehicleParamsEx(vid, engine, lights, alarm, doors, bonnet, boot, objective);
	new nextLocked = (doors == 1) ? 0 : 1;
	gServerVeh[idx][E_VEH_LOCKED] = (nextLocked == 1);
	SetVehicleParamsEx(vid, engine, lights, alarm, nextLocked, bonnet, boot, objective);

	new query[128];
	mysql_format(gSQL, query, sizeof query,
		"UPDATE `vehicles` SET `locked`=%d WHERE `id`=%d", nextLocked, gServerVeh[idx][E_VEH_DB_ID]);
	mysql_tquery(gSQL, query);
	return 1;
}

stock House_Create(idx, dbId, ownerCharId, Float:ex, Float:ey, Float:ez, Float:ix, Float:iy, Float:iz, intId)
{
	if (idx < 0 || idx >= MAX_HOUSES) return 0;

	gHouses[idx][E_HOUSE_ACTIVE] = true;
	gHouses[idx][E_HOUSE_DB_ID] = dbId;
	gHouses[idx][E_HOUSE_OWNER_CHAR_ID] = ownerCharId;
	gHouses[idx][E_HOUSE_LOCKED] = false;
	gHouses[idx][E_HOUSE_EXT_X] = ex;
	gHouses[idx][E_HOUSE_EXT_Y] = ey;
	gHouses[idx][E_HOUSE_EXT_Z] = ez;
	gHouses[idx][E_HOUSE_INT_X] = ix;
	gHouses[idx][E_HOUSE_INT_Y] = iy;
	gHouses[idx][E_HOUSE_INT_Z] = iz;
	gHouses[idx][E_HOUSE_INT_ID] = intId;
	gHouses[idx][E_HOUSE_PICKUP] = CreateDynamicPickup(1273, 1, ex, ey, ez, 0, 0);
	gHouses[idx][E_HOUSE_LABEL] = CreateDynamic3DTextLabel("Property", 0xFFFFFFFF, ex, ey, ez + 0.5, 20.0, .worldid = 0, .interiorid = 0);
	gHouses[idx][E_HOUSE_AREA] = CreateDynamicSphere(ex, ey, ez, 2.0, 0, 0);
	return 1;
}

stock House_Destroy(idx)
{
	if (idx < 0 || idx >= MAX_HOUSES || !gHouses[idx][E_HOUSE_ACTIVE]) return 0;
	gHouses[idx][E_HOUSE_ACTIVE] = false;

	if (IsValidDynamicPickup(gHouses[idx][E_HOUSE_PICKUP]))
		DestroyDynamicPickup(gHouses[idx][E_HOUSE_PICKUP]);
	if (IsValidDynamic3DTextLabel(gHouses[idx][E_HOUSE_LABEL]))
		DestroyDynamic3DTextLabel(gHouses[idx][E_HOUSE_LABEL]);
	if (IsValidDynamicArea(gHouses[idx][E_HOUSE_AREA]))
		DestroyDynamicArea(gHouses[idx][E_HOUSE_AREA]);
	gHouses[idx][E_HOUSE_PICKUP] = STREAMER_TAG_PICKUP:0;
	gHouses[idx][E_HOUSE_LABEL] = STREAMER_TAG_3D_TEXT_LABEL:0;
	gHouses[idx][E_HOUSE_AREA] = STREAMER_TAG_AREA:0;
	return 1;
}

stock House_Enter(playerid, idx)
{
	if (idx < 0 || idx >= MAX_HOUSES || !gHouses[idx][E_HOUSE_ACTIVE]) return 0;
	if (gHouses[idx][E_HOUSE_LOCKED] && gHouses[idx][E_HOUSE_OWNER_CHAR_ID] != gCharId[playerid]) return 0;

	new vw = VW_HOUSE_BASE + gHouses[idx][E_HOUSE_DB_ID];
	new interior = gHouses[idx][E_HOUSE_INT_ID];
	new Float:ix = gHouses[idx][E_HOUSE_INT_X];
	new Float:iy = gHouses[idx][E_HOUSE_INT_Y];
	new Float:iz = gHouses[idx][E_HOUSE_INT_Z];

	SetPlayerVirtualWorld(playerid, vw);
	SetPlayerInterior(playerid, interior);
	Streamer_UpdateEx(playerid, ix, iy, iz, vw, interior);
	SetPlayerPos(playerid, ix, iy, iz);
	return 1;
}

main() {}

public OnGameModeInit()
{
	gSQL = mysql_connect("127.0.0.1", "user", "password", "database");
	// Vehicle model 560 (Sultan); interior 3 (The Johnson house).
	Veh_CreatePersistent(0, 1, 1, 560, 1742.9, -1860.6, 13.57, 0.0, 1, 1, "LS-0001");
	House_Create(0, 1, 1, 1750.0, -1850.0, 13.57, 2496.0549, -1695.1749, 1014.7422, 3);
	return 1;
}

public OnGameModeExit()
{
	for (new i = 0; i < MAX_SERVER_VEHICLES; i++)
	{
		Veh_DestroyPersistent(i);
	}
	for (new i = 0; i < MAX_HOUSES; i++)
	{
		House_Destroy(i);
	}
	mysql_close(gSQL);
	return 1;
}

public OnPlayerConnect(playerid)
{
	gPlayerNearHouse[playerid] = -1;
	gCharId[playerid] = playerid + 1;
	return 1;
}

public OnPlayerDisconnect(playerid, reason)
{
	gPlayerNearHouse[playerid] = -1;
	gCharId[playerid] = 0;
	return 1;
}

public OnVehicleDeath(vehicleid, killerid)
{
	new idx = gVehByRuntime[vehicleid];
	if (idx >= 0)
	{
		gServerVeh[idx][E_VEH_DESTROYED] = true;
		gServerVeh[idx][E_VEH_ENGINE] = false;
		gServerVeh[idx][E_VEH_HEALTH] = 350.0;
	}
	return 1;
}

public OnVehicleSpawn(vehicleid)
{
	new idx = gVehByRuntime[vehicleid];
	if (idx >= 0)
	{
		SetVehicleNumberPlate(vehicleid, gServerVeh[idx][E_VEH_PLATE]);
		SetVehicleHealth(vehicleid, gServerVeh[idx][E_VEH_HEALTH]);
		new locked = gServerVeh[idx][E_VEH_LOCKED] ? 1 : 0;
		SetVehicleParamsEx(vehicleid, 0, 0, 0, locked, 0, 0, 0);
	}
	return 1;
}

public OnPlayerEnterDynamicArea(playerid, STREAMER_TAG_AREA:areaid)
{
	for (new i = 0; i < MAX_HOUSES; i++)
	{
		if (gHouses[i][E_HOUSE_ACTIVE] && gHouses[i][E_HOUSE_AREA] == areaid)
		{
			gPlayerNearHouse[playerid] = i;
			break;
		}
	}
	return 1;
}

public OnPlayerLeaveDynamicArea(playerid, STREAMER_TAG_AREA:areaid)
{
	new idx = gPlayerNearHouse[playerid];
	if (idx >= 0 && gHouses[idx][E_HOUSE_AREA] == areaid)
	{
		gPlayerNearHouse[playerid] = -1;
	}
	return 1;
}

cmd:engine(playerid, params[])
{
	#pragma unused params
	new vid = GetPlayerVehicleID(playerid);
	if (!Veh_ToggleEngine(playerid, vid))
		return SendClientMessage(playerid, -1, "You must be driving your own vehicle.");
	SendClientMessage(playerid, -1, "Engine toggled.");
	return 1;
}

cmd:lock(playerid, params[])
{
	#pragma unused params
	new vid = GetPlayerVehicleID(playerid);
	if (vid != 0 && gVehByRuntime[vid] >= 0)
	{
		if (Veh_ToggleLock(playerid, gVehByRuntime[vid]))
			return SendClientMessage(playerid, -1, "Vehicle lock toggled.");
	}
	for (new i = 0; i < MAX_SERVER_VEHICLES; i++)
	{
		if (Veh_ToggleLock(playerid, i))
			return SendClientMessage(playerid, -1, "Vehicle lock toggled.");
	}
	return SendClientMessage(playerid, -1, "No owned vehicle nearby.");
}

cmd:enter(playerid, params[])
{
	#pragma unused params
	new idx = gPlayerNearHouse[playerid];
	if (idx < 0 || !House_Enter(playerid, idx))
		return SendClientMessage(playerid, -1, "No unlocked property entrance nearby.");
	SendClientMessage(playerid, -1, "Entered property.");
	return 1;
}
