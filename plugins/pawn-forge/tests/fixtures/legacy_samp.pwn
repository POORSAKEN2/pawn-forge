// Fixture: a typical SA-MP 0.3.7 gamemode fragment that compiles against the
// SA-MP includes. tests/test_migrate.py migrates it and recompiles on open.mp.
#include <a_samp>

new Text:gClock;
new DB:gDB;

main() {}

public OnGameModeInit()
{
	gDB = db_open("server.db");
	db_free_result(db_query(gDB, "CREATE TABLE IF NOT EXISTS t (id INTEGER)"));
	gClock = TextDrawCreate(547.0, 24.0, "00:00");
	TextDrawFont(gClock, 3);
	TextDrawAlignment(gClock, 2);
	TextDrawColor(gClock, 0xFFFFFFFF);
	TextDrawBackgroundColor(gClock, 0x000000FF);
	TextDrawSetProportional(gClock, 1);
	TextDrawUseBox(gClock, 0);
	AddPlayerClass(0, 1958, 1343, 15, 270, 24, 100, 0, 0, 0, 0);
	return 1;
}

public OnPlayerSpawn(playerid)
{
	TogglePlayerControllable(playerid, 1);
	GivePlayerWeapon(playerid, 24, 50);
	TextDrawShowForPlayer(playerid, gClock);
	return 1;
}

public OnPlayerDeath(playerid, killerid, reason)
{
	for (new i = 0; i <= GetPlayerPoolSize(); i++)
	{
		if (IsPlayerConnected(i) && i == killerid) GivePlayerMoney(i, 100);
	}
	#pragma unused reason
	return 1;
}

public OnGameModeExit()
{
	db_close(gDB);
	return 1;
}
