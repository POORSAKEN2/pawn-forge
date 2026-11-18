# Factions, Overflow-Safe Economy & Proximity Chat

Keep faction permissions and duty gear isolated from civilian saves, guard every money mutation against integer overflow/underflow, and wrap proximity chat cleanly within SA-MP/open.mp's 144-character output cap.

## 1. Factions, Ranks & Duty Loadout Save/Restore

Model factions (`factions`, `faction_ranks`) with explicit types (`FACTION_TYPE_NONE`, `FACTION_TYPE_LEO`, `FACTION_TYPE_EMS`, `FACTION_TYPE_GOV`, `FACTION_TYPE_ILLEGAL`) and dynamic rank names (`MAX_FACTION_RANKS`).

### Duty Toggle Rules

Going on duty replaces a player's skin and weapons. If you overwrite them without saving civilian state first—or persist duty weapons on disconnect—players either lose their own guns or smuggle duty weapons into civilian play.

1. Require the player to be inside their faction's locker Streamer dynamic area (`OnPlayerEnterDynamicArea`) or faction HQ virtual world/interior.
2. **Going ON duty:**
   - Save civilian skin (`gChar[playerid][E_CHAR_OFFDUTY_SKIN] = GetPlayerSkin(playerid)`) and all 13 weapon slots via `GetPlayerWeaponData`.
   - Apply duty skin (verify IDs via `lookup kind=skin`, e.g., `280` Los Santos Police Officer Male, `306` Female), `SetPlayerColor`, `ResetPlayerWeapons`, `SetPlayerArmour(playerid, 100.0)`, and duty weapons via `lookup kind=weapon` (`WEAPON_NITESTICK` = 3, `WEAPON_DEAGLE` = 24, `WEAPON_M4` = 31).
3. **Going OFF duty (or on `OnPlayerDisconnect`):**
   - Call `ResetPlayerWeapons(playerid)`, restore saved civilian weapons (`if (ammo > 0 && weapon != WEAPON_FIST)`), restore `E_CHAR_OFFDUTY_SKIN`, reset colour, and clear `E_CHAR_ON_DUTY`.
   - Never write duty skin or duty weapons to the `characters` table.

```pawn
const MAX_WEAPON_SLOTS = 13;

enum E_SAVED_WEAPONS {
	WEAPON:E_SW_ID[MAX_WEAPON_SLOTS], // SA-MP 0.3.7: untagged E_SW_ID[MAX_WEAPON_SLOTS]
	E_SW_AMMO[MAX_WEAPON_SLOTS]
}
static gOffDutyWeapons[MAX_PLAYERS][E_SAVED_WEAPONS];

stock Faction_SaveCivilianLoadout(playerid)
{
	for (new slot = 0; slot < MAX_WEAPON_SLOTS; slot++)
	{
		new WEAPON:weap, ammo; // SA-MP 0.3.7: new weap, ammo;
		GetPlayerWeaponData(playerid, WEAPON_SLOT:slot, weap, ammo); // SA-MP: slot, weap, ammo
		gOffDutyWeapons[playerid][E_SW_ID][slot] = weap;
		gOffDutyWeapons[playerid][E_SW_AMMO][slot] = ammo;
	}
}

stock Faction_RestoreCivilianLoadout(playerid)
{
	ResetPlayerWeapons(playerid);
	for (new slot = 0; slot < MAX_WEAPON_SLOTS; slot++)
	{
		new WEAPON:weap = gOffDutyWeapons[playerid][E_SW_ID][slot];
		new ammo = gOffDutyWeapons[playerid][E_SW_AMMO][slot];
		if (ammo > 0 && weap != WEAPON_FIST)
			GivePlayerWeapon(playerid, weap, ammo);
		gOffDutyWeapons[playerid][E_SW_ID][slot] = WEAPON_FIST;
		gOffDutyWeapons[playerid][E_SW_AMMO][slot] = 0;
	}
}
```

Use verified faction vehicles (`lookup kind=vehicle`), e.g. `596` (LSPD car), `416` (Ambulance), `420` (Taxi), and verified HQ interiors (`lookup kind=interior`), e.g. Los Santos Police Department interior `6` at `(246.6695, 65.8039, 1003.6406)`.

## 2. Overflow-Safe Economy & `Money_Transfer`

Pawn cells are signed 32-bit integers (`cellmax == 2,147,483,647`). Adding unchecked cash wraps to negative numbers, and trusting `GetPlayerMoney()` lets cheaters forge cash.

- Keep `MAX_SAFE_MONEY = 1_000_000_000` (or `1000000000`).
- Sync HUD with `ResetPlayerMoney(playerid); GivePlayerMoney(playerid, gChar[playerid][E_CHAR_CASH]);` inside one helper `Money_SyncClient(playerid)`.
- Guard **every** `Money_Transfer(fromid, toid, amount)` with:
  1. Connected + logged-in + unlocked check (`!gChar[id][E_CHAR_SAVE_LOCK]`).
  2. `fromid != toid` and `amount > 0`.
  3. Underflow check: `if (gChar[fromid][E_CHAR_CASH] < amount) return false;`.
  4. Overflow check: `if (gChar[toid][E_CHAR_CASH] > MAX_SAFE_MONEY - amount || gChar[toid][E_CHAR_CASH] > cellmax - amount) return false;`.
  5. Mutate both in-memory balances, call `Money_SyncClient`, persist immediately (`mysql_tquery`), and insert an `economy_logs` audit record.

```pawn
const MAX_SAFE_MONEY = 1_000_000_000;

stock bool:Money_Transfer(fromid, toid, amount, const reason[] = "transfer")
{
	if (!IsPlayerConnected(fromid) || !IsPlayerConnected(toid) || fromid == toid) return false;
	if (!gChar[fromid][E_CHAR_LOGGED] || !gChar[toid][E_CHAR_LOGGED]) return false;
	if (gChar[fromid][E_CHAR_SAVE_LOCK] || gChar[toid][E_CHAR_SAVE_LOCK]) return false;
	if (amount <= 0) return false;
	if (gChar[fromid][E_CHAR_CASH] < amount) return false;
	if (gChar[toid][E_CHAR_CASH] > MAX_SAFE_MONEY - amount || gChar[toid][E_CHAR_CASH] > cellmax - amount)
		return false;

	gChar[fromid][E_CHAR_CASH] -= amount;
	gChar[toid][E_CHAR_CASH] += amount;

	Money_SyncClient(fromid);
	Money_SyncClient(toid);
	Char_SaveCritical(fromid);
	Char_SaveCritical(toid);
	Economy_LogTransfer(gChar[fromid][E_CHAR_ID], gChar[toid][E_CHAR_ID], amount, reason);
	return true;
}
```

## 3. Proximity Chat & Clean 2-Line 144-Char Wrapping

Client chat lines truncate at **144 characters** (`PF106`). Roleplay `/me`, `/do`, `/s` (shout), `/w` (whisper), and `/b` (local OOC) must:
1. Check `GetPlayerVirtualWorld(i) == vw && GetPlayerInterior(i) == interior` so players in different house virtual worlds never hear each other.
2. Compute 3D distance with `GetPlayerPos` + `VectorSize(x - tx, y - ty, z - tz) <= radius` (e.g., `3.5` whisper, `15.0` normal/`/me`/`/do`/`/b`, `30.0` shout).
3. Split lines over 144 characters at the last space before column `135`, emitting line 1 and `"... " + remainder` (capped to 144 chars each).

```pawn
stock Chat_SendWrapped(playerid, colour, const fullText[])
{
	new len = strlen(fullText);
	if (len <= 144)
	{
		SendClientMessage(playerid, colour, "%s", fullText); // SA-MP: SendClientMessage(playerid, colour, fullText)
		return 1;
	}

	new split = 136;
	while (split > 90 && fullText[split] != ' ')
		split--;
	if (fullText[split] != ' ')
		split = 136;

	new line1[145], line2[145];
	strmid(line1, fullText, 0, split, sizeof line1);
	new start2 = (fullText[split] == ' ') ? (split + 1) : split;
	format(line2, sizeof line2, "... %s", fullText[start2]);

	SendClientMessage(playerid, colour, "%s", line1);
	SendClientMessage(playerid, colour, "%s", line2);
	return 1;
}

stock Chat_SendNearby(senderid, Float:radius, colour, const text[])
{
	new Float:x, Float:y, Float:z, vw = GetPlayerVirtualWorld(senderid), interior = GetPlayerInterior(senderid);
	GetPlayerPos(senderid, x, y, z);

	foreach (new i : Player) // fallback without y_iterate: for (new i = 0; i < MAX_PLAYERS; i++) if (IsPlayerConnected(i))
	{
		if (!gChar[i][E_CHAR_LOGGED]) continue;
		if (GetPlayerVirtualWorld(i) != vw || GetPlayerInterior(i) != interior) continue;

		new Float:tx, Float:ty, Float:tz;
		GetPlayerPos(i, tx, ty, tz);
		if (VectorSize(x - tx, y - ty, z - tz) <= radius)
			Chat_SendWrapped(i, colour, text);
	}
	return 1;
}
```

Use `Pawn.CMD` + `sscanf2` for `/me`, `/do`, `/s`, `/w`, `/b`, validating non-empty input (`if (sscanf(params, "s[128]", text))`) and checking `target == INVALID_PLAYER_ID` + distance for `/w`.

## 4. SA-MP 0.3.7 vs open.mp Notes

- **`GetPlayerWeaponData` & `GivePlayerWeapon`:** open.mp tags slots/weapons with `WEAPON_SLOT:` and `WEAPON:`; SA-MP 0.3.7 uses untagged integers (`slot`, `weapon`).
- **`SendClientMessage`:** Never pass raw `line1` or user strings as the format argument on open.mp—use `SendClientMessage(playerid, colour, "%s", line1)`. On SA-MP 0.3.7 (`SendClientMessage(playerid, colour, const message[])`), `SendClientMessage` does not format at all, so `line1` is passed directly.
- **`VectorSize`:** Available natively in both SA-MP 0.3.7 (`a_samp.inc`) and open.mp (`omp_core.inc`).
- **Player iteration:** `foreach (new i : Player)` requires `<YSI_Data\y_iterate>`. Without YSI, `for (new i = 0; i < MAX_PLAYERS; i++) if (IsPlayerConnected(i))` is the clean cross-platform fallback (`GetPlayerPoolSize` is deprecated on open.mp).
