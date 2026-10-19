# Incognito's Streamer plugin

Confirm signatures with `api_lookup library=streamer`.

## Objects and maps

```pawn
#include <streamer>

new STREAMER_TAG_OBJECT:gGate;
gGate = CreateDynamicObject(980, 1500.0, -1700.0, 15.0, 0.0, 0.0, 90.0, .worldid = 0, .interiorid = 0);
MoveDynamicObject(gGate, 1500.0, -1700.0, 9.0, 2.0);
DestroyDynamicObject(gGate);
```

Static `CreateObject` is capped (1000 in SA-MP); the streamer only sends nearby items to each player.
Use `.worldid`/`.interiorid` named arguments so objects only stream where they belong.

## Teleporting onto mapped floors

```pawn
Streamer_UpdateEx(playerid, x, y, z, worldid, interiorid); // preloads and briefly freezes the player
SetPlayerPos(playerid, x, y, z);
```

## Areas, checkpoints, pickups, labels

```pawn
new STREAMER_TAG_AREA:gBankArea = CreateDynamicRectangle(1400.0, -1750.0, 1450.0, -1700.0);
public OnPlayerEnterDynamicArea(playerid, STREAMER_TAG_AREA:areaid) { if (areaid == gBankArea) { ... } return 1; }
public OnPlayerLeaveDynamicArea(playerid, STREAMER_TAG_AREA:areaid) { return 1; }

new STREAMER_TAG_CP:gJobCP = CreateDynamicCP(x, y, z, 3.0);
public OnPlayerEnterDynamicCP(playerid, STREAMER_TAG_CP:checkpointid) { ... return 1; }

CreateDynamicPickup(1239, 1, x, y, z);
CreateDynamic3DTextLabel("Bank", 0xFFFFFFFF, x, y, z + 0.5, 20.0);
```

With YSI, `hook` these callbacks per module.

## Rules

- Create world items once (init or when the owning entity is created) and destroy them with the entity.
- Store IDs with the right tag (`STREAMER_TAG_OBJECT`, `STREAMER_TAG_AREA`...).
- Prefer areas over polling `IsPlayerInRangeOfPoint` in timers.
