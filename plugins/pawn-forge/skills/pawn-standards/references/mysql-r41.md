# MySQL plugin R41 (pBlueG/SA-MP-MySQL)

Signatures below are from `a_mysql.inc`; confirm any other with `api_lookup library=mysql`.

## Connect once

```pawn
#include <a_mysql>

new MySQL:gSQL;

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

public OnGameModeExit()
{
	mysql_close(gSQL);
	return 1;
}
```

Keep credentials out of the source: `mysql_connect_file("mysql.ini")` reads them from a file in scriptfiles/.

## Threaded query with a race check

A player can disconnect (and someone else can take the slot) before the callback fires.
Increment a counter on connect and disconnect and pass it through:

```pawn
static gRace[MAX_PLAYERS];

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

public OnPlayerDisconnect(playerid, reason)
{
	gRace[playerid]++;
	return 1;
}

forward OnAccountLoaded(playerid, race);
public OnAccountLoaded(playerid, race)
{
	if (race != gRace[playerid]) return 0; // player left; the slot belongs to someone else now
	if (cache_num_rows() == 0)
	{
		// show registration
		return 1;
	}
	new id, cash;
	cache_get_value_name_int(0, "id", id);
	cache_get_value_name_int(0, "cash", cash);
	return 1;
}
```

## Rules

- `%e` for every quoted string value, `%d`/`%f` for numbers. Never `%s` inside quotes (lint PF202).
- Never build SQL with `format()` (PF201).
- `mysql_tquery` (ordered) or `mysql_pquery` (parallel pool) for gameplay. `mysql_query` blocks the server; if
  you must use it (e.g. on shutdown), `cache_delete` the returned cache (PF302/PF303).
- Cache functions (`cache_num_rows`, `cache_get_value_name*`, `cache_insert_id`) only work inside the query's
  callback, or on a cache you saved with `cache_save` and activated with `cache_set_active`.
- R41 has no server-side prepared statements. `mysql_format` + `%e`, or the ORM API (`orm_create`, `orm_addvar_*`,
  `orm_setkey`, `orm_select`/`orm_update`/`orm_insert`) is the safe parameterisation.
- Pre-R40 functions (`mysql_function_query`, `cache_get_data`, `cache_get_field_content`, `mysql_real_escape_string`,
  `mysql_store_result`, `mysql_fetch_row`...) are gone: port them (PF301).

## With YSI y_inline

`YSI_Extra\y_inline_mysql` provides `MySQL_TQueryInline(handle, using inline Name, query, ...)` so the callback
can live inline with the query. Use it when the project already uses YSI.
