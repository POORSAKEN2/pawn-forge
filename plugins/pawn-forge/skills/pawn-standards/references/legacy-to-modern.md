# Legacy to modern

| Legacy | Modern | Lint |
|---|---|---|
| `strtok` / `strcmp(cmdtext, "/cmd")` in `OnPlayerCommandText` | Pawn.CMD `cmd:` or YSI `YCMD:` + sscanf | PF501 |
| `dcmd`, zcmd/izcmd | Pawn.CMD (same `CMD:` syntax works) | PF502 |
| dini / dfile / dudb / DOF2 / y_ini accounts | MySQL R41 or SQLite | PF305 |
| `format(query, ..., "'%s'")` + query | `mysql_format` `%e`, SQLite `%q` | PF201/PF202 |
| `mysql_function_query`, `cache_get_field_content`, `mysql_store_result` | `mysql_tquery` + `cache_get_value_name*` | PF301 |
| `mysql_query` in gameplay | `mysql_tquery` with a callback | PF302 |
| `udb_hash`, Whirlpool, MD5, `SHA256_PassHash` | bcrypt | PF203 |
| `for (new i; i < MAX_PLAYERS; i++) if (IsPlayerConnected(i))` | `foreach (new i : Player)` | PF503 |
| `GetPlayerPoolSize()` | `MAX_PLAYERS` / foreach (deprecated on open.mp) | migrate |
| `new string[256]` everywhere | sized buffers; open.mp format-arg natives | PF107 |
| `format(s, 256, ...)` | `format(s, sizeof s, ...)` | PF101/PF102 |
| `sscanf(params, "us", ...)` | `"us[64]"` | PF105 |
| `SetTimer(..., true)` per player, ID discarded | stored ID + `KillTimer`, or y_timers `ptask` | PF401/PF402 |
| TextDraws created on every spawn | create once, show/hide (`convert_textdraws`) | PF403/PF404 |
| hundreds of `CreateObject` | Streamer `CreateDynamicObject` | PF406 |
| `ShowPlayerDialog(playerid, 1, ...)` | enum dialog IDs | PF505 |
| `#include <a_samp>` on open.mp | `#include <open.mp>` | PF506 / migrate |
| `TextDrawColor`, `db_query`, `GetServerVarAsInt`... | `TextDrawColour`, `DB_ExecuteQuery`, `GetConsoleVarAsInt` | migrate |
| `TogglePlayerControllable(id, 1)` | `TogglePlayerControllable(id, true)` | migrate |
| `GivePlayerWeapon(id, 24, 50)` | `GivePlayerWeapon(id, WEAPON_DEAGLE, 50)` | migrate |
| YSF / FCNPC / SKY on open.mp | built-in natives / NPC component / Pawn.RakNet | migrate |
| YSI 4 `YSI\y_hooks` | YSI 5 `YSI_Coding\y_hooks` | migrate |
