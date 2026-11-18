// Mirrors skills/pawn-roleplay/references/inventory-and-items.md.
// Needs: omp-stdlib, mysqlinc, samp-streamer-plugin, Pawn.CMD/src, sscanf.
#include <open.mp>
#include <a_mysql>
#include <streamer>
#include <Pawn.CMD>
#include <sscanf2>

#define MAX_INV_SLOTS 20
#define MAX_DROPS 64

const Float:MAX_INV_WEIGHT = 25.0;

enum {
	ITEM_NONE = 0,
	ITEM_WATER,
	ITEM_MEDKIT,
	ITEM_PHONE,
	ITEM_REPAIR_KIT
}

enum E_ITEM_META {
	E_IM_NAME[24],
	E_IM_MAX_STACK,
	Float:E_IM_WEIGHT,
	bool:E_IM_TRADEABLE
}

enum E_INV_SLOT {
	E_INV_TYPE,
	E_INV_QTY
}

enum E_DROP {
	bool:E_DROP_ACTIVE,
	E_DROP_TYPE,
	E_DROP_QTY,
	STREAMER_TAG_PICKUP:E_DROP_PICKUP,
	STREAMER_TAG_3D_TEXT_LABEL:E_DROP_LABEL
}

new const gItemMeta[][E_ITEM_META] = {
	{"None",       0, 0.0, false},
	{"Water",      5, 0.5, true},
	{"Medkit",     3, 1.2, true},
	{"Phone",      1, 0.3, true},
	{"Repair Kit", 2, 3.5, true}
};

new MySQL:gSQL;
static gRace[MAX_PLAYERS];
static gCharDbId[MAX_PLAYERS];
static gInv[MAX_PLAYERS][MAX_INV_SLOTS][E_INV_SLOT];
static bool:gInvLocked[MAX_PLAYERS];
static gDrops[MAX_DROPS][E_DROP];

stock Inv_ResetPlayer(playerid)
{
	gCharDbId[playerid] = 0;
	gInvLocked[playerid] = false;
	for (new s = 0; s < MAX_INV_SLOTS; s++)
	{
		gInv[playerid][s][E_INV_TYPE] = ITEM_NONE;
		gInv[playerid][s][E_INV_QTY] = 0;
	}
	return 1;
}

stock Float:Inv_GetWeight(playerid)
{
	new Float:total = 0.0;
	for (new s = 0; s < MAX_INV_SLOTS; s++)
	{
		new t = gInv[playerid][s][E_INV_TYPE];
		if (t > ITEM_NONE && t < sizeof gItemMeta)
		{
			total += gItemMeta[t][E_IM_WEIGHT] * float(gInv[playerid][s][E_INV_QTY]);
		}
	}
	return total;
}

stock bool:Inv_CanFit(playerid, itemType, amount)
{
	if (itemType <= ITEM_NONE || itemType >= sizeof gItemMeta || amount <= 0) return false;
	if (Inv_GetWeight(playerid) + gItemMeta[itemType][E_IM_WEIGHT] * float(amount) > MAX_INV_WEIGHT)
		return false;

	new remaining = amount;
	new maxStack = gItemMeta[itemType][E_IM_MAX_STACK];
	for (new s = 0; s < MAX_INV_SLOTS && remaining > 0; s++)
	{
		if (gInv[playerid][s][E_INV_TYPE] == itemType && gInv[playerid][s][E_INV_QTY] < maxStack)
		{
			remaining -= (maxStack - gInv[playerid][s][E_INV_QTY]);
		}
		else if (gInv[playerid][s][E_INV_TYPE] == ITEM_NONE)
		{
			remaining -= maxStack;
		}
	}
	return (remaining <= 0);
}

stock Inv_SaveSlot(playerid, slot)
{
	if (gCharDbId[playerid] <= 0 || slot < 0 || slot >= MAX_INV_SLOTS) return 0;

	new query[256];
	if (gInv[playerid][slot][E_INV_TYPE] == ITEM_NONE || gInv[playerid][slot][E_INV_QTY] <= 0)
	{
		mysql_format(gSQL, query, sizeof query,
			"DELETE FROM `character_items` WHERE `character_id`=%d AND `slot`=%d",
			gCharDbId[playerid], slot);
	}
	else
	{
		mysql_format(gSQL, query, sizeof query,
			"INSERT INTO `character_items` (`character_id`,`slot`,`item_type`,`quantity`) VALUES (%d,%d,%d,%d) ON DUPLICATE KEY UPDATE `item_type`=VALUES(`item_type`), `quantity`=VALUES(`quantity`)",
			gCharDbId[playerid], slot, gInv[playerid][slot][E_INV_TYPE], gInv[playerid][slot][E_INV_QTY]);
	}
	mysql_tquery(gSQL, query);
	return 1;
}

stock bool:Inv_Add(playerid, itemType, amount)
{
	if (!Inv_CanFit(playerid, itemType, amount)) return false;

	new remaining = amount;
	new maxStack = gItemMeta[itemType][E_IM_MAX_STACK];

	for (new s = 0; s < MAX_INV_SLOTS && remaining > 0; s++)
	{
		if (gInv[playerid][s][E_INV_TYPE] == itemType && gInv[playerid][s][E_INV_QTY] < maxStack)
		{
			new space = maxStack - gInv[playerid][s][E_INV_QTY];
			new add = (remaining < space) ? remaining : space;
			gInv[playerid][s][E_INV_QTY] += add;
			remaining -= add;
			Inv_SaveSlot(playerid, s);
		}
	}
	for (new s = 0; s < MAX_INV_SLOTS && remaining > 0; s++)
	{
		if (gInv[playerid][s][E_INV_TYPE] == ITEM_NONE)
		{
			new add = (remaining < maxStack) ? remaining : maxStack;
			gInv[playerid][s][E_INV_TYPE] = itemType;
			gInv[playerid][s][E_INV_QTY] = add;
			remaining -= add;
			Inv_SaveSlot(playerid, s);
		}
	}
	return true;
}

stock bool:Inv_RemoveFromSlot(playerid, slot, amount)
{
	if (slot < 0 || slot >= MAX_INV_SLOTS || amount <= 0) return false;
	if (gInv[playerid][slot][E_INV_TYPE] == ITEM_NONE || gInv[playerid][slot][E_INV_QTY] < amount)
		return false;

	gInv[playerid][slot][E_INV_QTY] -= amount;
	if (gInv[playerid][slot][E_INV_QTY] == 0)
	{
		gInv[playerid][slot][E_INV_TYPE] = ITEM_NONE;
	}
	Inv_SaveSlot(playerid, slot);
	return true;
}

stock bool:Inv_Transfer(fromid, toid, slot, amount)
{
	if (!IsPlayerConnected(fromid) || !IsPlayerConnected(toid) || fromid == toid) return false;
	if (gInvLocked[fromid] || gInvLocked[toid]) return false;
	if (slot < 0 || slot >= MAX_INV_SLOTS || amount <= 0) return false;

	new itemType = gInv[fromid][slot][E_INV_TYPE];
	if (itemType <= ITEM_NONE || itemType >= sizeof gItemMeta) return false;
	if (!gItemMeta[itemType][E_IM_TRADEABLE]) return false;
	if (gInv[fromid][slot][E_INV_QTY] < amount) return false;
	if (!Inv_CanFit(toid, itemType, amount)) return false;

	gInvLocked[fromid] = true;
	gInvLocked[toid] = true;

	Inv_RemoveFromSlot(fromid, slot, amount);
	Inv_Add(toid, itemType, amount);

	gInvLocked[fromid] = false;
	gInvLocked[toid] = false;
	return true;
}

stock Drop_Destroy(idx)
{
	if (idx < 0 || idx >= MAX_DROPS || !gDrops[idx][E_DROP_ACTIVE]) return 0;
	gDrops[idx][E_DROP_ACTIVE] = false;
	gDrops[idx][E_DROP_TYPE] = ITEM_NONE;
	gDrops[idx][E_DROP_QTY] = 0;

	if (IsValidDynamicPickup(gDrops[idx][E_DROP_PICKUP]))
		DestroyDynamicPickup(gDrops[idx][E_DROP_PICKUP]);
	if (IsValidDynamic3DTextLabel(gDrops[idx][E_DROP_LABEL]))
		DestroyDynamic3DTextLabel(gDrops[idx][E_DROP_LABEL]);
	gDrops[idx][E_DROP_PICKUP] = STREAMER_TAG_PICKUP:0;
	gDrops[idx][E_DROP_LABEL] = STREAMER_TAG_3D_TEXT_LABEL:0;
	return 1;
}

stock bool:Drop_Create(playerid, slot, amount)
{
	if (gInvLocked[playerid] || slot < 0 || slot >= MAX_INV_SLOTS || amount <= 0) return false;
	new itemType = gInv[playerid][slot][E_INV_TYPE];
	if (itemType <= ITEM_NONE || itemType >= sizeof gItemMeta) return false;
	if (gInv[playerid][slot][E_INV_QTY] < amount) return false;

	new idx = -1;
	for (new i = 0; i < MAX_DROPS; i++)
	{
		if (!gDrops[i][E_DROP_ACTIVE])
		{
			idx = i;
			break;
		}
	}
	if (idx == -1) return false;

	gInvLocked[playerid] = true;
	if (!Inv_RemoveFromSlot(playerid, slot, amount))
	{
		gInvLocked[playerid] = false;
		return false;
	}

	new Float:x, Float:y, Float:z, vw = GetPlayerVirtualWorld(playerid), interior = GetPlayerInterior(playerid);
	GetPlayerPos(playerid, x, y, z);

	new text[48];
	format(text, sizeof text, "%s (x%d)", gItemMeta[itemType][E_IM_NAME], amount);

	gDrops[idx][E_DROP_ACTIVE] = true;
	gDrops[idx][E_DROP_TYPE] = itemType;
	gDrops[idx][E_DROP_QTY] = amount;
	gDrops[idx][E_DROP_PICKUP] = CreateDynamicPickup(1279, 1, x, y, z - 0.3, vw, interior);
	gDrops[idx][E_DROP_LABEL] = CreateDynamic3DTextLabel(text, 0xFFFFFFFF, x, y, z, 10.0, .worldid = vw, .interiorid = interior);

	gInvLocked[playerid] = false;
	return true;
}

main() {}

public OnGameModeInit()
{
	gSQL = mysql_connect("127.0.0.1", "user", "password", "database");
	return 1;
}

public OnGameModeExit()
{
	for (new i = 0; i < MAX_DROPS; i++)
	{
		Drop_Destroy(i);
	}
	mysql_close(gSQL);
	return 1;
}

public OnPlayerConnect(playerid)
{
	gRace[playerid]++;
	Inv_ResetPlayer(playerid);
	gCharDbId[playerid] = playerid + 1;

	new query[160];
	mysql_format(gSQL, query, sizeof query,
		"SELECT `slot`, `item_type`, `quantity` FROM `character_items` WHERE `character_id`=%d LIMIT %d",
		gCharDbId[playerid], MAX_INV_SLOTS);
	mysql_tquery(gSQL, query, "OnInventoryLoaded", "dd", playerid, gRace[playerid]);
	return 1;
}

public OnPlayerDisconnect(playerid, reason)
{
	gRace[playerid]++;
	Inv_ResetPlayer(playerid);
	return 1;
}

forward OnInventoryLoaded(playerid, race);
public OnInventoryLoaded(playerid, race)
{
	if (race != gRace[playerid] || !IsPlayerConnected(playerid)) return 0;

	new rows = cache_num_rows();
	for (new r = 0; r < rows; r++)
	{
		new slot, itemType, qty;
		cache_get_value_name_int(r, "slot", slot);
		cache_get_value_name_int(r, "item_type", itemType);
		cache_get_value_name_int(r, "quantity", qty);
		if (slot >= 0 && slot < MAX_INV_SLOTS && itemType > ITEM_NONE && itemType < sizeof gItemMeta && qty > 0)
		{
			gInv[playerid][slot][E_INV_TYPE] = itemType;
			gInv[playerid][slot][E_INV_QTY] = qty;
		}
	}
	return 1;
}

public OnPlayerPickUpDynamicPickup(playerid, STREAMER_TAG_PICKUP:pickupid)
{
	if (gInvLocked[playerid]) return 1;
	for (new i = 0; i < MAX_DROPS; i++)
	{
		if (gDrops[i][E_DROP_ACTIVE] && gDrops[i][E_DROP_PICKUP] == pickupid)
		{
			new itemType = gDrops[i][E_DROP_TYPE];
			new qty = gDrops[i][E_DROP_QTY];
			if (!Inv_CanFit(playerid, itemType, qty))
				return SendClientMessage(playerid, -1, "Inventory full or too heavy."), 1;

			Drop_Destroy(i);
			Inv_Add(playerid, itemType, qty);
			SendClientMessage(playerid, -1, "Picked up %dx %s.", qty, gItemMeta[itemType][E_IM_NAME]);
			return 1;
		}
	}
	return 1;
}

cmd:giveitem(playerid, params[])
{
	new target, slot, amount;
	if (sscanf(params, "udd", target, slot, amount))
		return SendClientMessage(playerid, -1, "Usage: /giveitem [player] [slot] [amount]");
	if (target == INVALID_PLAYER_ID || target == playerid)
		return SendClientMessage(playerid, -1, "Invalid target player.");
	if (GetPlayerVirtualWorld(playerid) != GetPlayerVirtualWorld(target) || GetPlayerInterior(playerid) != GetPlayerInterior(target))
		return SendClientMessage(playerid, -1, "Target is not nearby.");

	new Float:x, Float:y, Float:z, Float:tx, Float:ty, Float:tz;
	GetPlayerPos(playerid, x, y, z);
	GetPlayerPos(target, tx, ty, tz);
	if (VectorSize(x - tx, y - ty, z - tz) > 4.0)
		return SendClientMessage(playerid, -1, "Target is too far away.");

	if (!Inv_Transfer(playerid, target, slot, amount))
		return SendClientMessage(playerid, -1, "Transfer failed.");

	SendClientMessage(playerid, -1, "Item transferred.");
	return 1;
}

cmd:dropitem(playerid, params[])
{
	new slot, amount;
	if (sscanf(params, "dd", slot, amount))
		return SendClientMessage(playerid, -1, "Usage: /dropitem [slot] [amount]");
	if (!Drop_Create(playerid, slot, amount))
		return SendClientMessage(playerid, -1, "Unable to drop item.");

	SendClientMessage(playerid, -1, "Item dropped.");
	return 1;
}
