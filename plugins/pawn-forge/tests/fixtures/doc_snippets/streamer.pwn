// Mirrors references/streamer.md. Needs: omp-stdlib, samp-streamer-plugin.
#include <open.mp>
#include <streamer>
new STREAMER_TAG_OBJECT:gGate;
new STREAMER_TAG_AREA:gBankArea;
new STREAMER_TAG_CP:gJobCP;
main() {}
public OnGameModeInit()
{
	gGate = CreateDynamicObject(980, 1500.0, -1700.0, 15.0, 0.0, 0.0, 90.0, .worldid = 0, .interiorid = 0);
	MoveDynamicObject(gGate, 1500.0, -1700.0, 9.0, 2.0);
	gBankArea = CreateDynamicRectangle(1400.0, -1750.0, 1450.0, -1700.0);
	gJobCP = CreateDynamicCP(1.0, 2.0, 3.0, 3.0);
	CreateDynamicPickup(1239, 1, 1.0, 2.0, 3.0);
	CreateDynamic3DTextLabel("Bank", 0xFFFFFFFF, 1.0, 2.0, 3.5, 20.0);
	return 1;
}
public OnGameModeExit() { DestroyDynamicObject(gGate); return 1; }
public OnPlayerEnterDynamicArea(playerid, STREAMER_TAG_AREA:areaid) { if (areaid == gBankArea) { } return 1; }
public OnPlayerLeaveDynamicArea(playerid, STREAMER_TAG_AREA:areaid) { return 1; }
public OnPlayerEnterDynamicCP(playerid, STREAMER_TAG_CP:checkpointid) { if (checkpointid == gJobCP) { } return 1; }
stock Teleport(playerid, Float:x, Float:y, Float:z, worldid, interiorid)
{
	Streamer_UpdateEx(playerid, x, y, z, worldid, interiorid);
	SetPlayerPos(playerid, x, y, z);
}
