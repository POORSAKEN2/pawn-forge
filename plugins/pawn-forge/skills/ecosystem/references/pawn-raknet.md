# Pawn.RakNet: BitStreams, Packets, and RPCs

`Pawn.RakNet` exposes raw RakNet incoming/outgoing packets and RPCs via `BitStream` handles (`#include <Pawn.RakNet>`). See `anticheat` (`references/raknet-and-nexac.md`) for full anti-cheat packet/RPC validation thresholds.

## 1. SA-MP 1.5.x vs open.mp `1.6.x-omp` Deployment

| Aspect | SA-MP 0.3.7 (`1.5.x`) | open.mp (`1.6.x-omp`) |
|---|---|---|
| Binary placement | `plugins/pawnraknet.dll` / `.so` in `server.cfg` | `components/Pawn.RakNet.dll` / `.so` (auto-loaded) |
| Legacy `SKY` plugin | Used alongside older scripts | Unsupported on open.mp; replace `SKY` hooks with `Pawn.RakNet` |
| Modern send natives | `PR_SendPacket`, `PR_SendRPC` (`BS_Send`/`BS_RPC` deprecated) | `PR_SendPacket`, `PR_SendRPC` |
| Modern outgoing callbacks | `OnOutgoingPacket`, `OnOutgoingRPC` (`OnOutcoming*` deprecated) | `OnOutgoingPacket`, `OnOutgoingRPC` |

## 2. BitStream Allocation & `PF801` Hygiene

Verify signatures with `api_lookup` (`library="pawn.raknet"`):
- `native BitStream:BS_New()`
- `native BitStream:BS_NewCopy(BitStream:bs)`
- `native BS_Delete(&BitStream:bs)`
- `native BS_Reset(BitStream:bs)`
- `native BS_ResetReadPointer(BitStream:bs)`
- `native BS_ResetWritePointer(BitStream:bs)`
- `native BS_ReadValue(BitStream:bs, {PR_ValueType, Float, _}:...)`
- `native BS_WriteValue(BitStream:bs, {PR_ValueType, Float, _}:...)`
- `native PR_SendPacket(BitStream:bs, playerid, PR_PacketPriority:priority = PR_HIGH_PRIORITY, PR_PacketReliability:reliability = PR_RELIABLE_ORDERED, orderingchannel = 0)`
- `native PR_SendRPC(BitStream:bs, playerid, rpcid, PR_PacketPriority:priority = PR_HIGH_PRIORITY, PR_PacketReliability:reliability = PR_RELIABLE_ORDERED, orderingchannel = 0)`

Rules:
1. **Free every allocated `BitStream` (`PF801`):** Every `BS_New()` or `BS_NewCopy()` **must** call `BS_Delete(bs)` on every exit path before returning.
2. **Never delete callback `BitStream` arguments:** The `BitStream:bs` passed to `OnIncomingPacket`, `OnIncomingRPC`, `OnOutgoingPacket`, `OnOutgoingRPC`, `IPacket:`, or `IRPC:` is owned by the plugin.
3. **Reset read pointers before continuing:** Whenever you read from a callback `BitStream` and return `1`, call `BS_ResetReadPointer(bs)` so the server (or downstream handlers) reads from bit `0`.

```pawn
#include <open.mp> // or <a_samp>
#include <Pawn.RakNet>

stock PR_SendCustomTextDrawHide(playerid, textdrawid)
{
	new BitStream:bs = BS_New();
	BS_WriteValue(bs, PR_UINT16, textdrawid);
	PR_SendRPC(bs, playerid, 135); // RPC_TextDrawHideForPlayer
	BS_Delete(bs); // Required: frees handle and satisfies PF801.
	return 1;
}

stock PR_CloneAndInspect(BitStream:src)
{
	new BitStream:copy = BS_NewCopy(src);
	new headerByte;
	BS_ReadValue(copy, PR_UINT8, headerByte);
	BS_Delete(copy); // Free on every path (PF801).
	return headerByte;
}
```

## 3. Global Callbacks vs `IPacket:` / `IRPC:` Handlers

Global callbacks receive every packet or RPC:
- `forward OnIncomingPacket(playerid, packetid, BitStream:bs)`
- `forward OnIncomingRPC(playerid, rpcid, BitStream:bs)`
- `forward OnOutgoingPacket(playerid, packetid, BitStream:bs)`
- `forward OnOutgoingRPC(playerid, rpcid, BitStream:bs)`

For targeted hooks, prefer `IPacket:` / `IRPC:` / `OPacket:` / `ORPC:` (or `PR_RegHandler(eventid, const publicname[], PR_EventType:type)`) so `Pawn.RakNet` only invokes Pawn for the specific ID instead of every network packet:

```pawn
const ID_PLAYER_SYNC    = 207;
const RPC_CLIENT_MSG    = 93;
const RPC_CHAT          = 101;

// Per-packet incoming handler (avoids Pawn overhead for unrelated packets)
IPacket:ID_PLAYER_SYNC(playerid, BitStream:bs)
{
	new bits;
	BS_GetNumberOfBitsUsed(bs, bits);
	if (bits < 552) return 0; // Drop malformed short sync packet

	new lr, ud, keys, Float:pos[3];
	BS_IgnoreBits(bs, 8); // Skip packet ID byte
	BS_ReadValue(bs, PR_UINT16, lr, PR_UINT16, ud, PR_UINT16, keys,
		PR_FLOAT, pos[0], PR_FLOAT, pos[1], PR_FLOAT, pos[2]);
	BS_ResetReadPointer(bs);

	if (pos[0] != pos[0] || pos[1] != pos[1] || pos[2] != pos[2])
		return 0; // Drop NaN crasher coordinates
	return 1;
}

// Per-RPC incoming handler
IRPC:RPC_CHAT(playerid, BitStream:bs)
{
	new len;
	BS_ReadValue(bs, PR_UINT8, len);
	BS_ResetReadPointer(bs);

	if (len > 144) return 0; // Drop oversized chat RPC
	return 1;
}

// Outgoing RPC hook example: intercept server-to-client SendClientMessage (RPC 93)
public OnOutgoingRPC(playerid, rpcid, BitStream:bs)
{
	if (rpcid == RPC_CLIENT_MSG)
	{
		new color, len;
		BS_ReadValue(bs, PR_UINT32, color, PR_UINT32, len);
		BS_ResetReadPointer(bs);
		// Inspect or return 0 to suppress delivery to playerid
		#pragma unused color, len
	}
	return 1;
}
```

## 4. Common Sync Packet Structures (`BS_ReadValue` / `BS_WriteValue`)

Common `PR_ValueType` specifiers in `Pawn.RakNet.inc`: `PR_INT8`, `PR_INT16`, `PR_INT32`, `PR_UINT8`, `PR_UINT16`, `PR_UINT32`, `PR_FLOAT`, `PR_BOOL`, `PR_STRING` (32-bit length prefix or paired with `PR_UINT8` length for short strings), `PR_BITS`. Always inspect exact bit layouts in `Pawn.RakNet.inc` (`api_lookup` / `project_dir`).

| Packet ID | Sync Struct | Key Fields (in order after 8-bit `packetId`) |
|---|---|---|
| `207` | `OnFootSync` (`ID_PLAYER_SYNC`) | `lrKey` (u16), `udKey` (u16), `keys` (u16), `position[3]` (f32x3), `quaternion[4]` (f32x4), `health` (u8), `armour` (u8), `additionalKeyWeapon` (u8), `specialAction` (u8), `velocity[3]` (f32x3), `surfingOffsets[3]` (f32x3), `surfingVehicleId` (u16), `animationId` (u16), `animationFlags` (u16) |
| `200` | `InCarSync` (`ID_VEHICLE_SYNC`) | `vehicleId` (u16), `lrKey` (u16), `udKey` (u16), `keys` (u16), `quaternion[4]` (f32x4), `position[3]` (f32x3), `velocity[3]` (f32x3), `vehicleHealth` (f32), `playerHealth` (u8), `armour` (u8), `additionalKeyWeapon` (u8), `sirenState` (u8), `landingGearState` (u8), `trailerId` (u16), `trainSpeed` (f32) |
| `211` | `PassengerSync` (`ID_PASSENGER_SYNC`) | `vehicleId` (u16), `seatFlags` (u8: low 6 bits = seat), `additionalKeyWeapon` (u8), `health` (u8), `armour` (u8), `lrKey` (u16), `udKey` (u16), `keys` (u16), `position[3]` (f32x3) |
| `206` | `BulletSync` (`ID_BULLET_SYNC`) | `hitType` (u8), `hitId` (u16), `origin[3]` (f32x3), `hitPos[3]` (f32x3), `offsets[3]` (f32x3), `weaponId` (u8) |
| `203` | `AimSync` (`ID_AIM_SYNC`) | `camMode` (u8), `camFrontVec[3]` (f32x3), `camPos[3]` (f32x3), `aimZ` (f32), `camZoomWeaponState` (u8), `aspectRatio` (u8) |

> **Modifying an incoming packet in-place:** Use `BS_SetWriteOffset(bs, bitOffset)` + `BS_WriteValue(...)`, then `BS_ResetReadPointer(bs)` before returning `1`—or allocate a clean outgoing packet with `BS_New()`, send with `PR_SendPacket`, and call `BS_Delete(bs)` (`PF801`).
