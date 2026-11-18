# ColAndreas & MapAndreas Physics / Raycasting

Use `ColAndreas` (`#include <colandreas>`) whenever the server needs 3D line-of-sight checks, bullet/wallbang verification, sloped surface placement, water detection, or collision against custom Streamer maps. Use `MapAndreas` only as a lightweight 2D heightmap fallback when 3D geometry is unnecessary.

## 1. ColAndreas Initialization & Core Natives

Verify signatures with `api_lookup` (`library="colandreas"`):
- `native CA_Init()`
- `native CA_RayCastLine(Float:StartX, Float:StartY, Float:StartZ, Float:EndX, Float:EndY, Float:EndZ, &Float:x, &Float:y, &Float:z)`
- `native CA_RayCastLineEx(Float:StartX, Float:StartY, Float:StartZ, Float:EndX, Float:EndY, Float:EndZ, &Float:x, &Float:y, &Float:z, &Float:rx, &Float:ry, &Float:rz, &Float:rw, &Float:cx, &Float:cy, &Float:cz)`
- `native CA_RayCastLineNormal(Float:startx, Float:starty, Float:startz, Float:endx, Float:endy, Float:endz, &Float:x, &Float:y, &Float:z, &Float:nx, &Float:ny, &Float:nz)`
- `native CA_CreateObject(modelid, Float:x, Float:y, Float:z, Float:rx, Float:ry, Float:rz, bool:add = false)`
- `native CA_DestroyObject(index)`
- `native CA_SetObjectPos(index, Float:x, Float:y, Float:z)`
- `native CA_SetObjectRot(index, Float:rx, Float:ry, Float:rz)`
- `native CA_RemoveBuilding(modelid, Float:x, Float:y, Float:z, Float:radius)`

> **`CA_FindZ_For2DCoord` note:** `CA_FindZ_For2DCoord(Float:x, Float:y, &Float:z)` is a `stock` helper in `colandreas.inc` implemented on top of `CA_RayCastLine(x, y, 700.0, x, y, -1000.0, x, y, z)` (which is why `api_lookup` returns `CA_RayCastLine` as the underlying native). Check its return value: `0` means no collision surface was found (e.g., void/under map).

```pawn
#include <open.mp> // or <a_samp>
#include <streamer>
#include <colandreas>

public OnGameModeInit()
{
	// Load any static custom map objects with add = false BEFORE CA_Init(),
	// then build the Bullet Physics BVH once in CA_Init():
	CA_Init();
	return 1;
}

stock bool:Physics_HasLineOfSight(Float:sx, Float:sy, Float:sz, Float:ex, Float:ey, Float:ez)
{
	new Float:hx, Float:hy, Float:hz;
	// Returns 0 when nothing blocks the ray between start and end.
	return CA_RayCastLine(sx, sy, sz, ex, ey, ez, hx, hy, hz) == 0;
}

stock bool:Physics_GetGroundZ(Float:x, Float:y, &Float:outZ)
{
	new Float:hx, Float:hy, Float:hz;
	if (CA_RayCastLine(x, y, 700.0, x, y, -1000.0, hx, hy, hz) != 0)
	{
		outZ = hz;
		return true;
	}
	return false;
}
```

## 2. Inspecting Hit Transform with `CA_RayCastLineEx`

When you need the hit object's center `(cx, cy, cz)` and rotation quaternion `(rx, ry, rz, rw)`—for example, aligning placed props, checking if a shot struck a dynamic door, or detecting whether a player is standing on a moved platform—use `CA_RayCastLineEx`:

```pawn
stock bool:Physics_TraceWithTransform(Float:sx, Float:sy, Float:sz, Float:ex, Float:ey, Float:ez, &Float:hx, &Float:hy, &Float:hz)
{
	new Float:rx, Float:ry, Float:rz, Float:rw, Float:cx, Float:cy, Float:cz;
	new model = CA_RayCastLineEx(sx, sy, sz, ex, ey, ez, hx, hy, hz, rx, ry, rz, rw, cx, cy, cz);
	#pragma unused rx, ry, rz, rw, cx, cy, cz
	return model != 0;
}
```

## 3. Syncing `ColAndreas` with Custom Streamer Maps

ColAndreas only knows default GTA SA geometry (`ColAndreas.cadb`) unless your map loader mirrors custom objects and removals:

1. **Startup bulk load:** Create Streamer objects and call `CA_CreateObject(modelid, x, y, z, rx, ry, rz, false)` before `CA_Init()`.
2. **Runtime objects (after `CA_Init()`):** Pass `add = true` (`CA_CreateObject(..., true)`) so the object enters the active Bullet world immediately, and store the returned `caIndex` alongside the `STREAMER_TAG_OBJECT` handle.
3. **Moved or deleted objects:** Call `CA_SetObjectPos` / `CA_SetObjectRot` when moving gates/elevators, and `CA_DestroyObject(caIndex)` when destroying the Streamer object.
4. **Removed GTA buildings:** Mirror every `RemoveBuildingForPlayer` with `CA_RemoveBuilding(modelid, x, y, z, radius)` before `CA_Init()` so raycasts do not collide with invisible deleted buildings.

```pawn
stock STREAMER_TAG_OBJECT:Map_CreateSolidObject(modelid, Float:x, Float:y, Float:z, Float:rx, Float:ry, Float:rz, &caIndex, worldid = 0, interiorid = 0)
{
	new STREAMER_TAG_OBJECT:obj = CreateDynamicObject(modelid, x, y, z, rx, ry, rz, .worldid = worldid, .interiorid = interiorid);
	caIndex = CA_CreateObject(modelid, x, y, z, rx, ry, rz, true);
	return obj;
}

stock Map_DestroySolidObject(&STREAMER_TAG_OBJECT:obj, &caIndex)
{
	if (IsValidDynamicObject(obj))
		DestroyDynamicObject(obj);
	if (caIndex != -1)
	{
		CA_DestroyObject(caIndex);
		caIndex = -1;
	}
	obj = STREAMER_TAG_OBJECT:0;
}
```

## 4. `MapAndreas` Lightweight Fallback

`MapAndreas` (`#include <MapAndreas>`, `MapAndreas_Init(MAP_ANDREAS_MODE_FULL)`, `MapAndreas_FindZ_For2DCoord(x, y, z)`) reads a flat 2D heightmap (`SAfull.hmap`):

| Feature | `ColAndreas` | `MapAndreas` |
|---|---|---|
| Full 3D raycast & line-of-sight | Yes (`CA_RayCastLine`) | No (vertical 2D heightmap only) |
| Bridges, tunnels, interiors, overhangs | Yes (returns exact roof/bridge layers) | No (single highest Z per `(x, y)`) |
| Custom `CreateDynamicObject` & `RemoveBuilding` sync | Yes (`CA_CreateObject`, `CA_RemoveBuilding`) | No |
| Memory / startup cost | Higher (`ColAndreas.cadb` + Bullet BVH) | Lower (`SAfull.hmap` / minimal mode) |

Use `MapAndreas` only on low-RAM servers that need simple outdoor terrain Z lookups without bridges, interiors, or line-of-sight checks.
