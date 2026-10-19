// Mirrors references/strings-and-buffers.md (SA-MP copy idiom). Needs: samp-stdlib, pawn-stdlib.
#include <a_samp>
new gPlayerTag[MAX_PLAYERS][16];
main() {}
public OnPlayerConnect(playerid)
{
	new tag[] = "VIP";
	gPlayerTag[playerid][0] = EOS;
	strcat(gPlayerTag[playerid], tag, sizeof gPlayerTag[]);
	return 1;
}
