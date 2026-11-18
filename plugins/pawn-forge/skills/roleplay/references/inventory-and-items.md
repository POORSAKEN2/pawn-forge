# Inventory, Items & Duplication-Proof Transfers

Model inventories relationally in SQL, keep item definitions in a `const` metadata table, validate slots, stacks, and weight before mutating state, and lock both players during transfers. See `plugins/pawn-forge/tests/fixtures/doc_snippets/rp_inventory.pwn` for a compilable `<open.mp>` reference.

## 1. Normalized `character_items` Schema

Never store inventories as comma-delimited strings (`"1,5,3|2,1,0"`) or `item1..item20` columns—string splitting truncates, cannot be queried atomically, and invites duplication bugs.

```sql
CREATE TABLE IF NOT EXISTS `character_items` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `character_id` INT UNSIGNED NOT NULL,
  `item_type` SMALLINT UNSIGNED NOT NULL,
  `quantity` INT UNSIGNED NOT NULL DEFAULT 1,
  `slot` TINYINT UNSIGNED NOT NULL,
  `durability` SMALLINT UNSIGNED NOT NULL DEFAULT 100,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_char_inv_slot` (`character_id`, `slot`),
  CONSTRAINT `fk_inv_char` FOREIGN KEY (`character_id`)
    REFERENCES `characters` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## 2. Static Item Metadata Table (`enum E_ITEM_META`)

Keep item rules in one read-only table indexed by item type enum so UI, weight calculations, stacking, and drops never drift out of sync:

```pawn
const MAX_INV_SLOTS = 20;
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
	bool:E_IM_TRADEABLE,
	bool:E_IM_DROPPABLE
}

new const gItemMeta[][E_ITEM_META] = {
	{"None",       0,  0.0, false, false},
	{"Water",      5,  0.5, true,  true},
	{"Medkit",     3,  1.2, true,  true},
	{"Phone",      1,  0.3, true,  true},
	{"Repair Kit", 2,  3.5, true,  true}
};
```

## 3. Slot, Weight & Stack Validation

Always pre-check capacity (`Inventory_CanFit`) **before** modifying any slot so an item add never succeeds partially and silently drops the remainder.

- **Bounds check:** `if (itemType <= ITEM_NONE || itemType >= sizeof gItemMeta || amount <= 0) return false;`
- **Weight check:** Sum `gItemMeta[type][E_IM_WEIGHT] * qty` across occupied slots (or maintain a cached carry weight updated inside `Inventory_Add` / `Inventory_Remove`) and require `currentWeight + addedWeight <= MAX_INV_WEIGHT`.
- **Stacking before free slots:** First scan existing slots with the same `itemType` for remaining stack room (`E_IM_MAX_STACK - qty`), then count free slots (`E_INV_TYPE == ITEM_NONE`) for the remainder.

## 4. Duplication-Proof `Inventory_Transfer`

Classic SA-MP RP item dupes happen when:
1. Two players trade or drop the same slot on the same tick before a DB write finishes.
2. A player disconnects or clicks `/giveitem` repeatedly while an async SQL query is in flight.
3. A transfer deducts from the sender without verifying the receiver has slot/weight room (or vice versa).

Prevent all three with a per-character lock (`gInvLocked[playerid]`), strict pre-validation, and atomic state mutation before persistence:

```pawn
stock bool:Inventory_Transfer(fromid, toid, slot, amount)
{
	if (!IsPlayerConnected(fromid) || !IsPlayerConnected(toid) || fromid == toid) return false;
	if (gInvLocked[fromid] || gInvLocked[toid]) return false;
	if (slot < 0 || slot >= MAX_INV_SLOTS || amount <= 0) return false;

	new itemType = gInv[fromid][slot][E_INV_TYPE];
	if (itemType <= ITEM_NONE || itemType >= sizeof gItemMeta) return false;
	if (!gItemMeta[itemType][E_IM_TRADEABLE]) return false;
	if (gInv[fromid][slot][E_INV_QTY] < amount) return false;
	if (!Inventory_CanFit(toid, itemType, amount)) return false;

	// Lock both sides around mutation + persistence
	gInvLocked[fromid] = true;
	gInvLocked[toid] = true;

	Inventory_RemoveFromSlot(fromid, slot, amount);
	Inventory_Add(toid, itemType, amount);
	Inventory_SaveSlot(fromid, slot);
	Inventory_SaveAllDirty(toid);

	gInvLocked[fromid] = false;
	gInvLocked[toid] = false;
	return true;
}
```

> **Note:** If you defer unlock until a `mysql_tquery` callback completes (`OnInventoryTransferred`), enforce a `gRace[playerid]` guard on the callback and unlock in `OnPlayerDisconnect` on reset so a failed query never permanently soft-locks a player slot.

## 5. Ground Drops with Streamer Pickups

- Pool drops in a bounded array `gDrops[MAX_DROPS][E_DROP]` storing `STREAMER_TAG_PICKUP:E_DROP_PICKUP`, `STREAMER_TAG_3D_TEXT_LABEL:E_DROP_LABEL`, `E_DROP_ITEM`, `E_DROP_QTY`, and `bool:E_DROP_ACTIVE`.
- In `OnPlayerPickUpDynamicPickup(playerid, STREAMER_TAG_PICKUP:pickupid)`:
  1. Check `!gInvLocked[playerid]` and `Inventory_CanFit(playerid, itemType, qty)`.
  2. Mark `gDrops[idx][E_DROP_ACTIVE] = false` and call `DestroyDynamicPickup` + `DestroyDynamic3DTextLabel` **before** calling `Inventory_Add`, eliminating race pickups.
  3. Destroy all active drop pickups/labels in `OnGameModeExit` (`PF405` clean).

## 6. SA-MP 0.3.7 vs open.mp Notes

- **String copies:** Use `strcopy(dest, src)` on open.mp; `strcat((dest[0] = EOS, dest), src, sizeof dest)` on SA-MP 0.3.7.
- **Weapon items:** When an inventory "use/equip" action equips a firearm, `GivePlayerWeapon` takes `WEAPON:weaponid` on open.mp (`WEAPON_DEAGLE`) vs untagged `int` on SA-MP 0.3.7 (`24` or `#define` constant). Verify weapon IDs via `lookup kind=weapon`.
- **Chat formatting:** open.mp `SendClientMessage` accepts direct format args; SA-MP 0.3.7 requires `format(msg, sizeof msg, ...)` into a `144`-cell buffer first.
