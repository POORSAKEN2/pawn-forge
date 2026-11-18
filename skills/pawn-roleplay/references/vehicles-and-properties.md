# Persistent Vehicles & Properties (Houses / Businesses)

Never store runtime `vehicleid` or Streamer entity IDs in SQL. Maintain explicit bidirectional mappings between persistent SQL `db_id` rows and runtime engine/Streamer handles, isolate shared interiors with per-property virtual worlds, and clean up every created entity. See `plugins/pawn-forge/tests/fixtures/doc_snippets/rp_vehicle_house.pwn` for a compilable `<open.mp>` reference.

## 1. Persistent `db_id` vs Runtime `vehicleid`

`CreateVehicle` returns a pooled `vehicleid` (`1..MAX_VEHICLES - 1`) that changes whenever vehicles spawn or despawn. Store a permanent `id` (`db_id`) in SQL (`vehicles` table) and keep an O(1) lookup table `gVehIndexByRuntime[MAX_VEHICLES]` initialized to `-1`.

```pawn
const MAX_SERVER_VEHICLES = 500;

enum E_SERVER_VEH {
	E_VEH_DB_ID,
	E_VEH_OWNER_CHAR_ID,
	E_VEH_MODEL,
	Float:E_VEH_X,
	Float:E_VEH_Y,
	Float:E_VEH_Z,
	Float:E_VEH_A,
	E_VEH_COL1,
	E_VEH_COL2,
	E_VEH_PLATE[16],
	E_VEH_RUNTIME_ID,
	E_VEH_FUEL,
	Float:E_VEH_HEALTH,
	bool:E_VEH_LOCKED,
	bool:E_VEH_ENGINE,
	bool:E_VEH_BOOT,
	bool:E_VEH_TRUNK_LOCKED,
	bool:E_VEH_DESTROYED
}

new gServerVeh[MAX_SERVER_VEHICLES][E_SERVER_VEH];
new gVehIndexByRuntime[MAX_VEHICLES];
```

Verify vehicle model IDs (`400..611`) with `lookup kind=vehicle` (e.g., `426` Premier, `560` Sultan, `482` Burrito) before creating vehicles (`PF601`).

## 2. `GetVehicleParamsEx` / `SetVehicleParamsEx`

Always read existing vehicle parameters before toggling one flag so lights, bonnet, boot, or alarm states are not overwritten:

```pawn
stock Veh_ToggleEngine(vehicleid)
{
	new idx = gVehIndexByRuntime[vehicleid];
	if (idx < 0 || idx >= MAX_SERVER_VEHICLES) return 0;

	new engine, lights, alarm, doors, bonnet, boot, objective;
	GetVehicleParamsEx(vehicleid, engine, lights, alarm, doors, bonnet, boot, objective);
	new nextEngine = (engine == 1) ? 0 : 1;
	gServerVeh[idx][E_VEH_ENGINE] = (nextEngine == 1);
	SetVehicleParamsEx(vehicleid, nextEngine, lights, alarm, doors, bonnet, boot, objective);
	return 1;
}
```

- **Key/ownership check:** Verify `gChar[playerid][E_CHAR_ID] == gServerVeh[idx][E_VEH_OWNER_CHAR_ID]` (or shared key / faction match) and `GetPlayerState(playerid) == PLAYER_STATE_DRIVER` before toggling engine.
- **Locking (`/lock`):** Check driver seat or proximity (`GetVehiclePos` + `VectorSize <= 4.0` + matching virtual world) and update both `doors` in `SetVehicleParamsEx` and `E_VEH_LOCKED`.

## 3. Trunk Inventories

Store trunk items in a normalized `vehicle_trunk_items` SQL table keyed by `vehicle_id` (`db_id`), **not** runtime `vehicleid`:
1. Require the player to be on foot, in the same virtual world, within `3.5` units of the vehicle (`GetVehiclePos` + `VectorSize`), and require `gServerVeh[idx][E_VEH_BOOT]` to be open (`boot == 1`).
2. Lock `gServerVeh[idx][E_VEH_TRUNK_LOCKED]` (and the player's `gInvLocked[playerid]`) during trunk transfers so two players standing at the same trunk cannot duplicate an item.
3. Release `E_VEH_TRUNK_LOCKED` when the player closes the dialog, walks away, or disconnects.

## 4. `OnVehicleDeath` & `OnVehicleSpawn` Recovery

By default, GTA destroys and respawns a vehicle at its creation point with factory health and unlocked doors—wiping RP damage, fuel, and impound state. Intercept both callbacks:

```pawn
public OnVehicleDeath(vehicleid, killerid)
{
	new idx = gVehIndexByRuntime[vehicleid];
	if (idx >= 0)
	{
		gServerVeh[idx][E_VEH_DESTROYED] = true;
		gServerVeh[idx][E_VEH_ENGINE] = false;
		gServerVeh[idx][E_VEH_HEALTH] = 350.0; // towed/repair threshold on recovery
	}
	return 1;
}

public OnVehicleSpawn(vehicleid)
{
	new idx = gVehIndexByRuntime[vehicleid];
	if (idx >= 0)
	{
		SetVehicleNumberPlate(vehicleid, gServerVeh[idx][E_VEH_PLATE]);
		SetVehicleHealth(vehicleid, gServerVeh[idx][E_VEH_HEALTH]);
		new locked = gServerVeh[idx][E_VEH_LOCKED] ? 1 : 0;
		SetVehicleParamsEx(vehicleid, 0, 0, 0, locked, 0, 0, 0);
	}
	return 1;
}
```

For full impound/insurance flows, destroy the wrecked runtime vehicle (`DestroyVehicle`), clear `gVehIndexByRuntime[vehicleid] = -1`, mark `impounded = 1` in SQL, and respawn with `CreateVehicle` only when retrieved.

## 5. Houses & Businesses: Pickups, Dynamic Areas & VW Isolation

Never poll `IsPlayerInRangeOfPoint` in `OnPlayerUpdate` (`PF802`). Attach one Streamer dynamic sphere, pickup, and 3D label per property on load, and track proximity via `OnPlayerEnterDynamicArea` / `OnPlayerLeaveDynamicArea`:

```pawn
const MAX_HOUSES = 200;
const VW_HOUSE_BASE = 10000;

enum E_HOUSE_DATA {
	E_HOUSE_DB_ID,
	E_HOUSE_OWNER_CHAR_ID,
	E_HOUSE_PRICE,
	bool:E_HOUSE_LOCKED,
	Float:E_HOUSE_EXT_X,
	Float:E_HOUSE_EXT_Y,
	Float:E_HOUSE_EXT_Z,
	E_HOUSE_EXT_VW,
	E_HOUSE_EXT_INT,
	Float:E_HOUSE_INT_X,
	Float:E_HOUSE_INT_Y,
	Float:E_HOUSE_INT_Z,
	E_HOUSE_INT_ID,
	STREAMER_TAG_PICKUP:E_HOUSE_PICKUP,
	STREAMER_TAG_3D_TEXT_LABEL:E_HOUSE_LABEL,
	STREAMER_TAG_AREA:E_HOUSE_AREA,
	bool:E_HOUSE_ACTIVE
}
```

- **Virtual world isolation:** Assign interior virtual world `VW_HOUSE_BASE + gHouse[idx][E_HOUSE_DB_ID]`. Multiple houses can safely share the same GTA interior without players seeing each other.
- **Verified interiors (`lookup kind=interior`):**
  - Safe house (*The Johnson house*): interior `3`, `(2496.0549, -1695.1749, 1014.7422)`
  - Safe house (*Safehouse 1*): interior `5`, `(2233.6919, -1112.8107, 1050.8828)`
  - Business (*24/7 1*): interior `17`, `(-25.722, -187.8216, 1003.5469)`
  - Police Dept (*Los Santos Police Department*): interior `6`, `(246.6695, 65.8039, 1003.6406)`
- **Safe teleport order:** Call `SetPlayerVirtualWorld`, `SetPlayerInterior`, and `Streamer_UpdateEx(playerid, x, y, z, vw, interior)` **before** `SetPlayerPos` so custom-mapped floors stream before gravity acts.
- **Cleanup (`PF405`):** Always call `DestroyDynamicPickup`, `DestroyDynamic3DTextLabel`, `DestroyDynamicArea`, and `DestroyVehicle` on entity removal and `OnGameModeExit`.

## 6. SA-MP 0.3.7 vs open.mp Notes

- **`SetVehicleParamsEx`:** open.mp defaults the 7 state parameters to `-1` (leave unchanged) and returns `bool:`. SA-MP 0.3.7 has **no defaults**—pass all 8 arguments every time (always `GetVehicleParamsEx` first).
- **`CreateVehicle`:** open.mp takes `bool:addSiren = false`; SA-MP 0.3.7 takes `addsiren = 0`.
- **`OnPlayerStateChange`:** open.mp uses `forward OnPlayerStateChange(playerid, PLAYER_STATE:newstate, PLAYER_STATE:oldstate);`; SA-MP 0.3.7 uses untagged `newstate, oldstate`.
