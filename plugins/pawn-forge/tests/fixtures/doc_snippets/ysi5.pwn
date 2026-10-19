// Mirrors references/ysi.md. Needs: omp-stdlib, YSI-Includes (+ deps).
#include <open.mp>
#include <YSI_Coding\y_hooks>
#include <YSI_Data\y_iterate>
#include <YSI_Coding\y_timers>
#include <YSI_Visual\y_commands>
#define MAX_HOUSES 100
new Iterator:Houses<MAX_HOUSES>;
main() {}
hook OnPlayerConnect(playerid) { return 1; }
task SaveAll[60000]() { foreach (new i : Player) { printf("%d", i); } }
ptask PlayerTick[1000](playerid) { }
timer RespawnLater[5000](playerid) { SpawnPlayer(playerid); }
YCMD:heal(playerid, params[], help)
{
	if (help) return SendClientMessage(playerid, -1, "Restores your health.");
	SetPlayerHealth(playerid, 100.0);
	return 1;
}
public OnPlayerSpawn(playerid)
{
	new houseid = Iter_Free(Houses);
	if (houseid != INVALID_ITERATOR_SLOT) Iter_Add(Houses, houseid);
	printf("%d %d", Iter_Count(Houses), Iter_Contains(Houses, houseid));
	Iter_Remove(Houses, houseid);
	defer RespawnLater(playerid);
	new Timer:t = repeat RespawnLater(playerid);
	stop t;
	return 1;
}
