// Mirrors references/commands-and-input.md. Needs: omp-stdlib, Pawn.CMD/src, sscanf.
#include <open.mp>
#include <Pawn.CMD>
#include <sscanf2>
enum (<<= 1) { CMD_USER = 1, CMD_ADMIN }
main() {}
cmd:kick(playerid, params[])
{
	new target, reason[64];
	if (sscanf(params, "uS(No reason)[64]", target, reason))
		return SendClientMessage(playerid, -1, "Usage: /kick [player] [reason]");
	if (target == INVALID_PLAYER_ID)
		return SendClientMessage(playerid, -1, "Player not found.");
	Kick(target);
	return 1;
}
alias:kick("k")
flags:kick(CMD_ADMIN)
public OnPlayerCommandReceived(playerid, cmd[], params[], flags)
{
	if ((flags & CMD_ADMIN) && !IsPlayerAdmin(playerid)) return 0;
	return 1;
}
public OnPlayerCommandPerformed(playerid, cmd[], params[], result, flags) { return 1; }
