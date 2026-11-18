# Accounts, Authentication & Character Spawning

Use relational tables (`accounts` -> `characters`), `samp-bcrypt` for passwords, `gRace[playerid]` counters on every async callback, and staggered dirty-flag saves. See `pawn-standards` (`references/mysql-r41.md`) and `pawn-modernize-storage` for DB baseline rules.

## 1. Multi-Character SQL Schema (MySQL R41)

Separate login credentials (`accounts`) from in-game personas (`characters`). Never store plain passwords, and never mix runtime `playerid` into SQL.

```sql
CREATE TABLE IF NOT EXISTS `accounts` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `username` VARCHAR(25) NOT NULL,
  `password_hash` CHAR(60) NOT NULL,
  `admin_level` TINYINT UNSIGNED NOT NULL DEFAULT 0,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `last_login` TIMESTAMP NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_accounts_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `characters` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `account_id` INT UNSIGNED NOT NULL,
  `name` VARCHAR(25) NOT NULL,
  `skin` SMALLINT UNSIGNED NOT NULL DEFAULT 26,
  `cash` INT NOT NULL DEFAULT 500,
  `bank_cash` INT NOT NULL DEFAULT 2500,
  `health` FLOAT NOT NULL DEFAULT 100.0,
  `armour` FLOAT NOT NULL DEFAULT 0.0,
  `interior` TINYINT UNSIGNED NOT NULL DEFAULT 0,
  `virtual_world` INT NOT NULL DEFAULT 0,
  `pos_x` FLOAT NOT NULL DEFAULT 1742.9,
  `pos_y` FLOAT NOT NULL DEFAULT -1860.6,
  `pos_z` FLOAT NOT NULL DEFAULT 13.57,
  `pos_angle` FLOAT NOT NULL DEFAULT 0.0,
  `faction_id` INT UNSIGNED NOT NULL DEFAULT 0,
  `faction_rank` TINYINT UNSIGNED NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_characters_name` (`name`),
  KEY `idx_characters_account` (`account_id`),
  CONSTRAINT `fk_char_account` FOREIGN KEY (`account_id`)
    REFERENCES `accounts` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## 2. Async Race Guards (`gRace[playerid]`)

Players can disconnect and another player can reuse the same `playerid` slot before a threaded MySQL query or bcrypt worker completes. Increment `gRace[playerid]` in **both** `OnPlayerConnect` and `OnPlayerDisconnect`, pass it through `"d"`/`"dd"`, and check it first inside every async callback.

```pawn
#include <open.mp> // or <a_samp> on SA-MP 0.3.7
#include <a_mysql>
#include <streamer>
#include <samp_bcrypt>

const BCRYPT_COST = 12;
const MAX_LOGIN_ATTEMPTS = 3;

enum {
	DIALOG_NONE = 0,
	DIALOG_REGISTER,
	DIALOG_LOGIN,
	DIALOG_CHAR_SELECT
}

enum E_CHAR_DATA {
	E_CHAR_ACC_ID,
	E_CHAR_ID,
	E_CHAR_SKIN,
	E_CHAR_CASH,
	E_CHAR_BANK,
	Float:E_CHAR_HP,
	Float:E_CHAR_ARMOUR,
	E_CHAR_INT,
	E_CHAR_VW,
	Float:E_CHAR_X,
	Float:E_CHAR_Y,
	Float:E_CHAR_Z,
	Float:E_CHAR_A,
	bool:E_CHAR_LOGGED,
	bool:E_CHAR_DIRTY,
	bool:E_CHAR_SAVE_LOCK
}

new MySQL:gSQL;
new gChar[MAX_PLAYERS][E_CHAR_DATA];
static gRace[MAX_PLAYERS];
static gLoginAttempts[MAX_PLAYERS];
static gStoredHash[MAX_PLAYERS][BCRYPT_HASH_LENGTH];
```

Reset per-player state completely on connect and disconnect:

```pawn
static Char_ResetState(playerid)
{
	static const emptyChar[E_CHAR_DATA];
	gChar[playerid] = emptyChar;
	gLoginAttempts[playerid] = 0;
	gStoredHash[playerid][0] = EOS;
}

public OnPlayerConnect(playerid)
{
	gRace[playerid]++;
	Char_ResetState(playerid);
	TogglePlayerSpectating(playerid, true);

	new name[MAX_PLAYER_NAME + 1], query[128];
	GetPlayerName(playerid, name, sizeof name);
	mysql_format(gSQL, query, sizeof query,
		"SELECT `id`, `password_hash` FROM `accounts` WHERE `username` = '%e' LIMIT 1", name);
	mysql_tquery(gSQL, query, "OnAccountLookup", "dd", playerid, gRace[playerid]);
	return 1;
}

public OnPlayerDisconnect(playerid, reason)
{
	if (gChar[playerid][E_CHAR_LOGGED])
	{
		Char_SaveCritical(playerid);
	}
	gRace[playerid]++;
	Char_ResetState(playerid);
	return 1;
}
```

## 3. `samp-bcrypt` Auth Flow & Zero-Trust Dialogs

Verify `samp-bcrypt` callbacks with `api_lookup`:
- `bcrypt_hash(playerid, const callback[], const input[], cost, const args[] = "", {Float, _}:...)`
- `bcrypt_verify(playerid, const callback[], const input[], const hash[], const args[] = "", {Float, _}:...)`
- `bcrypt_get_hash(hash[], size = sizeof(hash))`

Always guard `isnull(inputtext)` / `!inputtext[0]` before `strcmp` (`PF702`), validate password length (`6..64`), and delay `Kick` after sending an error message (`PF701`).

```pawn
forward DelayedKick(playerid, race);
public DelayedKick(playerid, race)
{
	if (race == gRace[playerid] && IsPlayerConnected(playerid))
		Kick(playerid);
	return 1;
}

static Auth_KickDelayed(playerid, const msg[])
{
	SendClientMessage(playerid, 0xE74C3CFF, "%s", msg); // SA-MP: SendClientMessage(playerid, 0xE74C3CFF, msg)
	SetTimerEx("DelayedKick", 250, false, "dd", playerid, gRace[playerid]);
	return 1;
}

forward OnAccountLookup(playerid, race);
public OnAccountLookup(playerid, race)
{
	if (race != gRace[playerid] || !IsPlayerConnected(playerid)) return 0;

	if (cache_num_rows() == 0)
	{
		ShowPlayerDialog(playerid, DIALOG_REGISTER, DIALOG_STYLE_PASSWORD,
			"Register", "Enter a password (6-64 chars):", "Create", "Quit");
		return 1;
	}
	cache_get_value_name_int(0, "id", gChar[playerid][E_CHAR_ACC_ID]);
	cache_get_value_name(0, "password_hash", gStoredHash[playerid], BCRYPT_HASH_LENGTH);
	ShowPlayerDialog(playerid, DIALOG_LOGIN, DIALOG_STYLE_PASSWORD,
		"Login", "Enter your account password:", "Login", "Quit");
	return 1;
}

public OnDialogResponse(playerid, dialogid, response, listitem, inputtext[])
{
	switch (dialogid)
	{
		case DIALOG_REGISTER:
		{
			if (!response) return Auth_KickDelayed(playerid, "Registration cancelled.");
			new len = strlen(inputtext);
			if (len < 6 || len > 64)
			{
				ShowPlayerDialog(playerid, DIALOG_REGISTER, DIALOG_STYLE_PASSWORD,
					"Register", "Password must be 6-64 characters:", "Create", "Quit");
				return 1;
			}
			bcrypt_hash(playerid, "OnAccountPassHashed", inputtext, BCRYPT_COST, "d", gRace[playerid]);
			return 1;
		}
		case DIALOG_LOGIN:
		{
			if (!response) return Auth_KickDelayed(playerid, "Login cancelled.");
			if (!inputtext[0])
			{
				ShowPlayerDialog(playerid, DIALOG_LOGIN, DIALOG_STYLE_PASSWORD,
					"Login", "Password cannot be empty:", "Login", "Quit");
				return 1;
			}
			bcrypt_verify(playerid, "OnAccountPassVerified", inputtext, gStoredHash[playerid], "d", gRace[playerid]);
			return 1;
		}
	}
	return 0;
}

forward OnAccountPassHashed(playerid, race);
public OnAccountPassHashed(playerid, race)
{
	if (race != gRace[playerid] || !IsPlayerConnected(playerid)) return 0;

	new hash[BCRYPT_HASH_LENGTH], name[MAX_PLAYER_NAME + 1], query[256];
	bcrypt_get_hash(hash, sizeof hash);
	GetPlayerName(playerid, name, sizeof name);

	mysql_format(gSQL, query, sizeof query,
		"INSERT INTO `accounts` (`username`, `password_hash`) VALUES ('%e', '%e')", name, hash);
	mysql_tquery(gSQL, query, "OnAccountInserted", "dd", playerid, gRace[playerid]);
	return 1;
}

forward OnAccountPassVerified(playerid, bool:success, race);
public OnAccountPassVerified(playerid, bool:success, race)
{
	if (race != gRace[playerid] || !IsPlayerConnected(playerid)) return 0;

	if (!success)
	{
		if (++gLoginAttempts[playerid] >= MAX_LOGIN_ATTEMPTS)
			return Auth_KickDelayed(playerid, "Too many failed login attempts.");

		ShowPlayerDialog(playerid, DIALOG_LOGIN, DIALOG_STYLE_PASSWORD,
			"Login", "Incorrect password. Try again:", "Login", "Quit");
		return 1;
	}
	// Clear stored hash from memory and query characters for DIALOG_CHAR_SELECT
	gStoredHash[playerid][0] = EOS;
	new query[160];
	mysql_format(gSQL, query, sizeof query,
		"SELECT `id`, `name`, `skin`, `cash` FROM `characters` WHERE `account_id` = %d LIMIT 5",
		gChar[playerid][E_CHAR_ACC_ID]);
	mysql_tquery(gSQL, query, "OnCharacterListLoaded", "dd", playerid, gRace[playerid]);
	return 1;
}
```

## 4. Staggered Dirty-Flag Auto-Save vs Immediate Critical Writes

Saving 200 players in a single 5-minute timer spikes the MySQL thread pool and causes hitching. Instead:
- **Dirty-flag staggered saves:** Mark `gChar[playerid][E_CHAR_DIRTY] = true` on non-critical changes (position, health, playtime). Run a 1-second cursor tick (saving e.g. 5–10 dirty connected players per tick) so writes spread evenly across the interval.
- **Immediate critical writes:** Save immediately on cash/bank transfers, item grants/trades, vehicle/house purchases, password changes, and `OnPlayerDisconnect`.

```pawn
stock Char_SaveCritical(playerid)
{
	if (!gChar[playerid][E_CHAR_LOGGED] || gChar[playerid][E_CHAR_ID] <= 0) return 0;

	GetPlayerPos(playerid, gChar[playerid][E_CHAR_X], gChar[playerid][E_CHAR_Y], gChar[playerid][E_CHAR_Z]);
	GetPlayerFacingAngle(playerid, gChar[playerid][E_CHAR_A]);
	GetPlayerHealth(playerid, gChar[playerid][E_CHAR_HP]);
	GetPlayerArmour(playerid, gChar[playerid][E_CHAR_ARMOUR]);
	gChar[playerid][E_CHAR_INT] = GetPlayerInterior(playerid);
	gChar[playerid][E_CHAR_VW] = GetPlayerVirtualWorld(playerid);
	gChar[playerid][E_CHAR_DIRTY] = false;

	new query[320];
	mysql_format(gSQL, query, sizeof query,
		"UPDATE `characters` SET `cash`=%d, `bank_cash`=%d, `skin`=%d, `health`=%.2f, `armour`=%.2f, `interior`=%d, `virtual_world`=%d, `pos_x`=%.4f, `pos_y`=%.4f, `pos_z`=%.4f, `pos_angle`=%.2f WHERE `id`=%d",
		gChar[playerid][E_CHAR_CASH], gChar[playerid][E_CHAR_BANK], gChar[playerid][E_CHAR_SKIN],
		gChar[playerid][E_CHAR_HP], gChar[playerid][E_CHAR_ARMOUR], gChar[playerid][E_CHAR_INT],
		gChar[playerid][E_CHAR_VW], gChar[playerid][E_CHAR_X], gChar[playerid][E_CHAR_Y],
		gChar[playerid][E_CHAR_Z], gChar[playerid][E_CHAR_A], gChar[playerid][E_CHAR_ID]);
	mysql_tquery(gSQL, query);
	return 1;
}
```

## 5. Safe Spawn State (`Streamer_UpdateEx`)

When spawning a loaded character:
1. Disable spectator mode (`TogglePlayerSpectating(playerid, false)`), or configure `SetSpawnInfo` then call `SpawnPlayer(playerid)`.
2. In `OnPlayerSpawn(playerid)`, reject unauthenticated spawns (`if (!gChar[playerid][E_CHAR_LOGGED]) return 0;`).
3. Apply `SetPlayerVirtualWorld` and `SetPlayerInterior` **before** `SetPlayerPos`.
4. Call `Streamer_UpdateEx(playerid, x, y, z, vw, interior)` before `SetPlayerPos` so Streamer preloads dynamic mapped floors and briefly freezes the player to prevent falling through custom interiors.
5. Sync `SetPlayerFacingAngle`, `SetCameraBehindPlayer`, `SetPlayerSkin`, `SetPlayerHealth`, `SetPlayerArmour`, and `ResetPlayerMoney` + `GivePlayerMoney`.

## 6. SA-MP 0.3.7 vs open.mp Notes

- **Strings:** Use `strcopy(dest, src)` on open.mp; use `strcat((dest[0] = EOS, dest), src, sizeof dest)` on SA-MP 0.3.7.
- **Formatting in natives:** open.mp `SendClientMessage` and `ShowPlayerDialog` accept trailing format arguments directly (`SendClientMessage(playerid, col, "%s", msg)`). On SA-MP 0.3.7, format into a `new msg[144];` buffer first (`format(msg, sizeof msg, ...)`).
- **`SetSpawnInfo`:** On open.mp, default weapons use `WEAPON_FIST` (`WEAPON:` tag). On SA-MP 0.3.7, pass `0, 0, 0, 0, 0, 0`.
- **SQLite alternative:** If using SQLite instead of MySQL R41, use `%q` for strings and free **every** result with `DB_FreeResultSet` (open.mp) or `db_free_result` (SA-MP 0.3.7).
