new gStats[10];

forward ShowStats(playerid, targetid);
public ShowStats(playerid, targetid)
{
	new slot = targetid + 9;
	#pragma unused playerid
	gStats[slot] = 1;
	return 1;
}

CMD:stats(playerid, params[])
{
	#pragma unused params
	return ShowStats(playerid, playerid);
}
