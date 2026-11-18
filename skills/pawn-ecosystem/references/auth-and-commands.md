# Authentication (`samp-bcrypt`), Command Processors, `sscanf2`, & Dialog Helpers

Verify exact signatures with `api_lookup` / `pawnforge api --project-dir .` before writing auth or command code—two incompatible bcrypt plugins exist in the SA-MP/open.mp ecosystem.

## 1. Password Hashing: `samp-bcrypt` vs `bcrypt-samp`

Never use `udb_hash`, MD5, Whirlpool, or `SHA256_PassHash` (`PF502`).

### Primary Standard: `Sreyas-Sreelal/samp-bcrypt` (`#include <samp_bcrypt>`)

Verified signatures (`library="samp-bcrypt"`):
- `native bcrypt_hash(playerid, const callback[], const input[], cost, const args[] = "", {Float, _}:...)`
- `native bcrypt_verify(playerid, const callback[], const input[], const hash[], const args[] = "", {Float, _}:...)`
- `native bcrypt_get_hash(hash[], size = sizeof(hash))`
- `native bcrypt_set_thread_limit(value)`

Use cost `10`–`12`, store hashes in `CHAR(60)` (`BCRYPT_HASH_LENGTH` = `61`), and pass a `gRace[playerid]` counter in `args[]` (`"d"`) to reject stale callbacks if a player disconnects before the worker thread finishes:

```pawn
#include <open.mp> // or <a_samp>
#include <samp_bcrypt>

const BCRYPT_COST = 12;
static gRace[MAX_PLAYERS];

public OnPlayerConnect(playerid) { gRace[playerid]++; return 1; }
public OnPlayerDisconnect(playerid, reason) { gRace[playerid]++; return 1; }

stock Auth_HashPassword(playerid, const password[])
{
	bcrypt_hash(playerid, "OnAuthHashed", password, BCRYPT_COST, "d", gRace[playerid]);
}

forward OnAuthHashed(playerid, race);
public OnAuthHashed(playerid, race)
{
	if (race != gRace[playerid] || !IsPlayerConnected(playerid)) return 0;
	new hash[BCRYPT_HASH_LENGTH];
	bcrypt_get_hash(hash, sizeof hash);
	// Persist hash to MySQL with mysql_format + %e
	return 1;
}

stock Auth_CheckPassword(playerid, const password[], const storedHash[])
{
	bcrypt_verify(playerid, "OnAuthVerified", password, storedHash, "d", gRace[playerid]);
}

forward OnAuthVerified(playerid, bool:success, race);
public OnAuthVerified(playerid, bool:success, race)
{
	if (race != gRace[playerid] || !IsPlayerConnected(playerid)) return 0;
	if (!success) return SendClientMessage(playerid, 0xFF4444FF, "Wrong password.");
	return 1;
}
```

### Alternative: `lassir/bcrypt-samp` (`#include <bcrypt>`)

Projects using `lassir/bcrypt-samp` (`#include <bcrypt>`) instead of `<samp_bcrypt>` have a **different** API:
- Hashing: `bcrypt_hash(callback[], const args[], const data[], cost, ...)` (callback comes **first**, no `playerid` arg unless passed in `args[]`).
- Verifying: `bcrypt_check(callback[], const args[], const data[], const hash[])`, then call `bool:bcrypt_is_equal()` inside the verify callback instead of receiving `bool:success` as a parameter.
- Always run `api_lookup` / `pawnforge api --project-dir .` to confirm which header is installed before writing auth callbacks.

## 2. Command Processors: `Pawn.CMD` vs `YCMD` vs `I-ZCMD`

| Processor | Backing | Strengths | Handler Syntax |
|---|---|---|---|
| `Pawn.CMD` (`<Pawn.CMD>`) | C++ plugin / `3.4.0-omp` component | Fastest dispatch, `flags:`, `alias:`, `PC_*` runtime API | `cmd:ban(playerid, params[])` |
| `YCMD` (`<YSI_Visual\y_commands>`) | Pure Pawn (YSI 5) | Built-in `y_groups` permissions, `help` arg, no binary | `YCMD:ban(playerid, params[], help)` |
| `I-ZCMD` (`<izcmd>`) | Pure Pawn (legacy) | Simple drop-in for legacy SA-MP scripts | `CMD:ban(playerid, params[])` |

Verified `Pawn.CMD` natives/callbacks (`library="pawn.cmd"`):
- `forward OnPlayerCommandReceived(playerid, cmd[], params[], flags)` (return `0` to deny before execution)
- `forward OnPlayerCommandPerformed(playerid, cmd[], params[], result, flags)`
- `PC_RegAlias`, `PC_SetFlags`, `PC_GetFlags`, `PC_CommandExists`, `PC_EmulateCommand`

```pawn
#include <Pawn.CMD>
#include <sscanf2>

enum (<<= 1) { CMD_PLAYER = 1, CMD_MOD }

cmd:givewep(playerid, params[])
{
	new target, weaponid, ammo;
	if (sscanf(params, "uk<weapon>I(100)", target, weaponid, ammo))
		return SendClientMessage(playerid, -1, "Usage: /givewep [player] [weapon] [ammo=100]");
	if (target == INVALID_PLAYER_ID)
		return SendClientMessage(playerid, -1, "Player not found.");
	if (ammo < 1 || ammo > 5000)
		return SendClientMessage(playerid, -1, "Invalid ammo range.");
	GivePlayerWeapon(target, WEAPON:weaponid, ammo);
	return 1;
}
alias:givewep("gw")
flags:givewep(CMD_MOD)
```

## 3. Advanced `sscanf2` Specifiers (`2.13.8+` in `components/` on open.mp)

Verified signature (`library="sscanf"`): `native sscanf(const data[], const format[], {T_WEAPON, Float, _}:...)`

Always pass explicit `[size]` on every `s` / `S` string specifier (`PF105`). Useful advanced specifiers:

| Specifier | Purpose | Example |
|---|---|---|
| `k<weapon>` | Built-in weapon name or ID (`WEAPON_DEAGLE`, `"deagle"`, `"24"`) | `"uk<weapon>i"` |
| `k<vehicle>` | Custom `SSCANF:vehicle(const string[])` converter (name or model `400..611`) | `"k<vehicle>I(1)I(1)"` |
| `e<E_ENUM>` | Fill a Pawn `enum` struct directly from delimited text | `"e<E_SPAWN_CFG>"` |
| `p<delim>` | Override whitespace delimiter (e.g., CSV or pipe-delimited fields) | `"p<,>fff"` |
| `a<type>[N]` | Fixed-size array of up to `N` values | `"a<i>[4]"` |
| `?` / `{...}` | Quietly skip a token without storing it | `"{s[16]}i"` |

## 4. `easyDialog` & `mSelection`

- **`easyDialog` (`#include <easyDialog>`):** Named dialog handlers (`Dialog:ConfirmBuy(playerid, response, listitem, inputtext[])`, `Dialog_Show(playerid, ConfirmBuy, DIALOG_STYLE_MSGBOX, ...)`) without a giant `OnDialogResponse` switch. Use `y_dialog` (`Dialog_ShowCallback`) instead if you already include YSI 5; in both, still guard `response`, `listitem` bounds, and `isnull(inputtext)` (`PF702`).
- **`mSelection` (`#include <mSelection>`):** File-driven model preview menus (`LoadModelSelectionMenu`, `ShowModelSelectionMenu`, `OnPlayerModelSelection`). For modern open.mp servers needing custom layouts without external list files, build native `TEXT_DRAW_FONT_MODEL_PREVIEW` (`PlayerTextDrawSetPreviewModel`) grids using `pawn-textdraw`.
