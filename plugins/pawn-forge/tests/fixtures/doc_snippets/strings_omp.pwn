// Mirrors references/strings-and-buffers.md (open.mp parts). Needs: omp-stdlib.
#include <open.mp>
enum E_PLAYER { E_PLAYER_NAME[MAX_PLAYER_NAME + 1], E_PLAYER_CASH }
new gPlayer[MAX_PLAYERS][E_PLAYER];
new gPlayerTag[MAX_PLAYERS][16];
main() {}
stock bool:IsAdminName(const name[]) { return name[0] == '@'; }
public OnPlayerConnect(playerid)
{
	new msg[144], name[MAX_PLAYER_NAME + 1], amount = 5, tag[] = "VIP";
	GetPlayerName(playerid, name, sizeof name);
	format(msg, sizeof msg, "%s paid $%d", name, amount);
	SendClientMessage(playerid, 0xFFFFFFFF, "%s paid $%d", name, amount);
	strcopy(gPlayerTag[playerid], tag);
	GetPlayerName(playerid, gPlayer[playerid][E_PLAYER_NAME], MAX_PLAYER_NAME + 1);
	printf("%d %s", IsAdminName(name), msg);
	return 1;
}
