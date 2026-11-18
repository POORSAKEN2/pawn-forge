# Streamer & World Management (`samp-streamer-plugin`)

This guide extends `pawn-standards` (`references/streamer.md`) with server-wide capacity tuning, dynamic area shapes, object/area attachments, per-player targeting, and `PF802`-compliant proximity tracking. See `plugins/pawn-forge/tests/fixtures/doc_snippets/eco_streamer_areas.pwn` for a compiled reference snippet.

## 1. Global Tuning & Client Limits

Verify signatures with `api_lookup` (`library="streamer"`):
- `native Streamer_SetMaxItems(type, items)`
- `native Streamer_SetVisibleItems(type, items, playerid = -1)`
- `native Streamer_SetTickRate(rate)`
- `native Streamer_SetCellDistance(Float:distance)`
- `native Streamer_SetCellSize(Float:size)`
- `native Streamer_UpdateEx(playerid, Float:x, Float:y, Float:z, worldid = -1, interiorid = -1, type = -1, compensatedtime = -1, freezeplayer = 1)`

Keep visible client counts below SA-MP/open.mp hard limits (`1000` objects, `4096` pickups, `1024` 3D labels, `100` map icons):

```pawn
public OnGameModeInit()
{
	Streamer_SetMaxItems(STREAMER_TYPE_OBJECT, 50000);
	Streamer_SetVisibleItems(STREAMER_TYPE_OBJECT, 700);  // Leave headroom below 1000-object client cap
	Streamer_SetVisibleItems(STREAMER_TYPE_3D_TEXT_LABEL, 512);
	Streamer_SetTickRate(50);                             // Streamer ticks every 50 server ticks
	Streamer_SetCellDistance(300.0);                      // Spatial grid query radius
	return 1;
}
```

## 2. Typed Handles & Dynamic Area Shapes

Always store returned IDs with their `STREAMER_TAG_*` tags (`STREAMER_TAG_OBJECT`, `STREAMER_TAG_AREA`, `STREAMER_TAG_CP`, `STREAMER_TAG_RACE_CP`, `STREAMER_TAG_PICKUP`, `STREAMER_TAG_3D_TEXT_LABEL`, `STREAMER_TAG_MAP_ICON`, `STREAMER_TAG_ACTOR`) so the compiler catches handle mix-ups.

Verified area constructors:
- `native STREAMER_TAG_AREA:CreateDynamicCircle(Float:x, Float:y, Float:radius, worldid = -1, interiorid = -1, playerid = -1, priority = 0)`
- `native STREAMER_TAG_AREA:CreateDynamicSphere(Float:x, Float:y, Float:z, Float:radius, worldid = -1, interiorid = -1, playerid = -1, priority = 0)`
- `native STREAMER_TAG_AREA:CreateDynamicCuboid(Float:minx, Float:miny, Float:minz, Float:maxx, Float:maxy, Float:maxz, worldid = -1, interiorid = -1, playerid = -1, priority = 0)`
- `native STREAMER_TAG_AREA:CreateDynamicPolygon(const Float:points[], Float:minz = -FLOAT_INFINITY, Float:maxz = FLOAT_INFINITY, maxpoints = sizeof points, worldid = -1, interiorid = -1, playerid = -1, priority = 0)`

`CreateDynamicPolygon` takes a **flat 1D array** of alternating `x, y` pairs (`Float:points[] = { x0, y0, x1, y1, ... }`), bounded vertically by `minz` and `maxz`:

```pawn
static const Float:sSafeZonePoly[] = {
	1450.0, -1750.0,
	1520.0, -1750.0,
	1520.0, -1680.0,
	1450.0, -1680.0
};

new STREAMER_TAG_AREA:gSafeZone;
new STREAMER_TAG_AREA:gGarageSphere;
new STREAMER_TAG_AREA:gRadarCircle;
new STREAMER_TAG_AREA:gVaultCuboid;

stock World_CreateZones()
{
	gSafeZone = CreateDynamicPolygon(sSafeZonePoly, 0.0, 50.0, .worldid = 0, .interiorid = 0);
	gGarageSphere = CreateDynamicSphere(1500.0, -1700.0, 13.5, 4.0, .worldid = 0, .interiorid = 0);
	gRadarCircle = CreateDynamicCircle(1200.0, -1400.0, 35.0, .worldid = 0);
	gVaultCuboid = CreateDynamicCuboid(2140.0, 1605.0, 990.0, 2150.0, 1615.0, 1000.0, .worldid = 1, .interiorid = 1);
}
```

## 3. Attachments, Visibility (`E_STREAMER_PLAYER_ID`) & Metadata (`E_STREAMER_EXTRA_ID`)

Verified attachment & data natives:
- `native AttachDynamicObjectToVehicle(STREAMER_TAG_OBJECT:objectid, vehicleid, Float:offsetx, Float:offsety, Float:offsetz, Float:rx, Float:ry, Float:rz)`
- `native AttachDynamicAreaToPlayer(STREAMER_TAG_AREA:areaid, playerid, Float:offsetx = 0.0, Float:offsety = 0.0, Float:offsetz = 0.0)`
- `native Streamer_SetIntData(type, STREAMER_ALL_TAGS:id, data, value)`
- `native Streamer_GetIntData(type, STREAMER_ALL_TAGS:id, data)`

Use `AttachDynamicObjectToVehicle` for sirens, roof bars, or cargo crates, and `AttachDynamicAreaToPlayer` for moving proximity rings (e.g., taser/cuff aura or squad beacon) without per-frame polling.

Keep Streamer's two player-related data keys distinct:
- **`E_STREAMER_PLAYER_ID`** controls **per-player visibility** (`-1` = visible to all players, or a specific `playerid` to restrict/retarget visibility dynamically).
- **`E_STREAMER_EXTRA_ID`** stores **custom integer metadata** (such as an owning `playerid` or SQL ID) without affecting visibility.

```pawn
stock World_AttachSiren(vehicleid, &STREAMER_TAG_OBJECT:outObj)
{
	outObj = CreateDynamicObject(18646, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0);
	AttachDynamicObjectToVehicle(outObj, vehicleid, -0.4, 0.1, 0.82, 0.0, 0.0, 0.0);
}

stock World_CreatePersonalBeacon(playerid, &STREAMER_TAG_AREA:outArea)
{
	// .playerid = -1 keeps the area visible to everyone; E_STREAMER_EXTRA_ID tracks the owner.
	outArea = CreateDynamicSphere(0.0, 0.0, 0.0, 5.0, .playerid = -1);
	AttachDynamicAreaToPlayer(outArea, playerid);
	Streamer_SetIntData(STREAMER_TYPE_AREA, outArea, E_STREAMER_EXTRA_ID, playerid);
}

stock World_GetBeaconOwner(STREAMER_TAG_AREA:areaid)
{
	if (!IsValidDynamicArea(areaid)) return INVALID_PLAYER_ID;
	return Streamer_GetIntData(STREAMER_TYPE_AREA, areaid, E_STREAMER_EXTRA_ID);
}
```

> Clean up attached areas in `OnPlayerDisconnect` (`DestroyDynamicArea`) and vehicle-attached objects before `DestroyVehicle` (`DestroyDynamicObject`), resetting handles to `STREAMER_TAG_AREA:0` / `STREAMER_TAG_OBJECT:0`.

## 4. Teleport Preloading (`Streamer_UpdateEx`) & `PF802` Compliance

- **Never poll `IsPlayerInRangeOfPoint` inside `OnPlayerUpdate` (`PF802`).** `OnPlayerUpdate` runs ~30 times/sec per player. Use `OnPlayerEnterDynamicArea` / `OnPlayerLeaveDynamicArea` and `IsPlayerInDynamicArea(playerid, areaid)` when handling key presses or commands.
- **Preload mapped floors before teleporting:** Set `SetPlayerVirtualWorld` and `SetPlayerInterior`, call `Streamer_UpdateEx(playerid, x, y, z, worldid, interiorid)` (which freezes the player briefly while streaming objects at the destination), and then call `SetPlayerPos(playerid, x, y, z)`.
