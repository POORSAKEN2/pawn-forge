// Fixture: a deliberately bad, 2012-style gamemode. Every block should trigger
// the rule named in its comment. Used by tests/test_lint.py.
#include <a_samp>
#include <dini>
#include <zcmd>

#define DIALOG_LOGIN 1

new MySQL:gSQL;
new gTimer;

main() {}

public OnGameModeInit()
{
	SetTimer("Tick", 1000, true);                                  // fine: one global timer at init
	gTimer = SetTimer("Save", 60000, true);                        // PF402 (never killed)
	CreateVehicle(399, 0.0, 0.0, 3.0, 0.0, -1, -1, 60);            // PF601
	AddPlayerClass(74, 0.0, 0.0, 3.0, 0.0);                        // PF602
	return 1;
}

public OnPlayerConnect(playerid)
{
	new name[16], msg[64], query[128];
	GetPlayerName(playerid, name, sizeof(name));                   // PF103
	format(msg, sizeof(query), "Welcome %s", name);                // PF101
	format(msg, 128, "Welcome %s", name);                          // PF102
	format(msg, sizeof msg, "Welcome %s (%d)", name);              // PF104 (error: missing arg)
	format(query, sizeof query, "SELECT * FROM users WHERE name = '%s'", name); // PF201
	mysql_tquery(gSQL, query);
	mysql_format(gSQL, query, sizeof query, "SELECT id FROM users WHERE name = '%s'", name); // PF202
	new Cache:r = mysql_query(gSQL, query);                        // PF302 + PF303
	#pragma unused r
	new DBResult:res = db_query(DB:1, "SELECT 1");                 // PF304
	#pragma unused res
	SetTimerEx("Kick2", 100, false, "ii", playerid);               // PF104 (spec)
	SetTimerEx("PlayerTick", 1000, true, "i", playerid);           // PF401
	ShowPlayerDialog(playerid, 1, DIALOG_STYLE_INPUT, "Login", "Password:", "OK", "");  // PF505
	return 1;
}

public OnPlayerSpawn(playerid)
{
	new PlayerText:t = CreatePlayerTextDraw(playerid, 320.0, 240.0, "HUD"); // PF404
	#pragma unused t
	new Text:g = TextDrawCreate(10.0, 10.0, "x");                  // PF403
	#pragma unused g
	CreateDynamicObject(1337, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0);       // PF405
	GivePlayerWeapon(playerid, 20, 100);                           // PF603
	SetPlayerSkin(playerid, 312);                                  // PF602
	ApplyAnimation(playerid, "PED", "WALK_civi_x", 4.1, false, false, false, false, 0); // PF604
	ApplyAnimation(playerid, "PEDS", "WALK_civi", 4.1, false, false, false, false, 0);  // PF604 (library)
	new pass[64];
	udb_hash(pass);                                                // PF203
	dini_Set("users.ini", "pass", pass);                           // file storage: reported once, on the #include
	return 1;
}

public OnPlayerCommandText(playerid, cmdtext[])
{
	new cmd[128], idx;
	cmd = strtok(cmdtext, idx);                                    // PF501
	if (strcmp(cmd, "/help", true) == 0) { return 1; }             // PF501
	return 0;
}

CMD:pm(playerid, params[])
{
	new target, text[128];
	if (sscanf(params, "us", target, text)) return 1;              // PF105
	new big[5000];                                                 // PF107
	#pragma unused big
	SendClientMessage(playerid, -1, "This message is far too long for the SA-MP client chat box which truncates anything beyond one hundred and forty four characters, so the end of this sentence will never be seen by anyone");  // PF106
	return 1;
}

public OnPlayerUpdate(playerid)
{
	for (new i = 0; i < MAX_PLAYERS; i++) { }                      // PF503 + PF504
	return 1;
}

stock Suppressed(playerid)
{
	new n[8];
	GetPlayerName(playerid, n, sizeof n); // pawnforge-ignore PF103
	// pawnforge-ignore-next-line
	format(n, 100, "x");
	mysql_function_query(gSQL, "x", false, "", "");                // PF301
	return 1;
}
