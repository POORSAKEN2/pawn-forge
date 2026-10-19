// Mirrors skills/pawn-standards/references/mysql-r41.md. Needs: omp-stdlib, a_mysql.
#include <open.mp>
#include <a_mysql>
new MySQL:gSQL;
static gRace[MAX_PLAYERS];
main() {}
public OnGameModeInit()
{
	new MySQLOpt:opt = mysql_init_options();
	mysql_set_option(opt, AUTO_RECONNECT, true);
	gSQL = mysql_connect("127.0.0.1", "user", "password", "database", opt);
	if (gSQL == MYSQL_INVALID_HANDLE || mysql_errno(gSQL) != 0)
	{
		print("MySQL connection failed; shutting down.");
		SendRconCommand("exit");
		return 1;
	}
	return 1;
}
public OnGameModeExit() { mysql_close(gSQL); return 1; }
public OnPlayerConnect(playerid)
{
	gRace[playerid]++;
	new name[MAX_PLAYER_NAME + 1], query[128];
	GetPlayerName(playerid, name, sizeof name);
	mysql_format(gSQL, query, sizeof query,
		"SELECT `id`, `cash` FROM `players` WHERE `name` = '%e' LIMIT 1", name);
	mysql_tquery(gSQL, query, "OnAccountLoaded", "dd", playerid, gRace[playerid]);
	return 1;
}
public OnPlayerDisconnect(playerid, reason) { gRace[playerid]++; return 1; }
forward OnAccountLoaded(playerid, race);
public OnAccountLoaded(playerid, race)
{
	if (race != gRace[playerid]) return 0;
	if (cache_num_rows() == 0) return 1;
	new id, cash;
	cache_get_value_name_int(0, "id", id);
	cache_get_value_name_int(0, "cash", cash);
	printf("%d %d", id, cash);
	new Cache:c = cache_save();
	cache_set_active(c);
	if (cache_is_valid(c)) cache_delete(c);
	return 1;
}
