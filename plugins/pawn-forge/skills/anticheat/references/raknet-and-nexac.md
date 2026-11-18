# Pawn.RakNet Packet/RPC Filtering & Nex-AC Integration

Callback-level checks (`OnPlayerWeaponShot`, `OnDialogResponse`) run *after* RakNet has already unpacked client data. `Pawn.RakNet` lets you drop malformed packets, crasher floats (`NaN`/`Inf`), invalid seats, and forged RPCs at the network boundary.

> **Deployment:** On **open.mp**, place the open.mp `Pawn.RakNet` component build in `components/`. On **SA-MP 0.3.7**, load `pawnraknet` in `plugins/`. See `ecosystem` for full `Pawn.RakNet` setup and `BitStream` patterns.

## 1. BitStream Hygiene (`PF801`) & Pointer Resets

1. **Never leak allocated `BitStream` handles (`PF801`):** Every `BS_New()` or `BS_NewCopy()` call **must** be paired with `BS_Delete(bs)` on every exit path.
2. **Never call `BS_Delete(bs)` on callback parameters:** The `BitStream:bs` passed into `OnIncomingPacket` / `OnIncomingRPC` / `PR_RegHandler` callbacks is owned by the plugin.
3. **Always reset read offsets:** Call `BS_ResetReadPointer(bs)` before returning `1`, otherwise the server reads from your leftover offset and corrupts player state.

```pawn
stock AC_SendSafeClientRPC(playerid, rpcid, value)
{
	new BitStream:bs = BS_New();
	BS_WriteValue(bs, PR_INT32, value);
	BS_RPC(bs, playerid, rpcid);
	BS_Delete(bs); // Required: prevents BitStream handle leak (PF801).
	return 1;
}
```

## 2. Incoming Packet Validation (`OnIncomingPacket`)

Return `0` to drop a packet before SA-MP/open.mp processes or relays it to streamed players; return `1` after `BS_ResetReadPointer(bs)` to allow it.

| Packet ID | Name | Minimum Bits | Critical Checks |
|---|---|---|---|
| `207` | Player Sync (`ID_PLAYER_SYNC`) | `552` (69 bytes) | Finite `pos[3]`, `quat[4]`, `vel[3]`, `surfOffset[3]`; `\|pos\| <= 20000.0` |
| `200` | Vehicle Sync (`ID_VEHICLE_SYNC`) | `512` (64 bytes) | Valid `vehicleId` (`1..MAX_VEHICLES - 1`), `trailerId != vehicleId`, finite `pos`/`vel`/`quat`/`carHealth` |
| `211` | Passenger Sync (`ID_PASSENGER_SYNC`) | `200` (25 bytes) | Valid `vehicleId`, valid passenger seat (`1 <= (seatByte & 0x3F) <= 7`), finite `pos[3]` |
| `206` | Bullet Sync (`ID_BULLET_SYNC`) | `328` (41 bytes) | `hitType <= 4`, finite `origin[3]`/`hitPos[3]`/`offsets[3]`, `\|coord\| <= 20000.0` |

```pawn
#include <open.mp> // or <a_samp>
#include <Pawn.RakNet>

const ID_VEHICLE_SYNC   = 200;
const ID_BULLET_SYNC    = 206;
const ID_PLAYER_SYNC    = 207;
const ID_PASSENGER_SYNC = 211;

static stock bool:AC_ValidCoord3(const Float:v[3], Float:limit = 20000.0)
{
	for (new i = 0; i < 3; i++)
	{
		if (v[i] != v[i] || floatabs(v[i]) > limit) return false;
	}
	return true;
}

static stock bool:AC_ValidFinite4(const Float:q[4])
{
	for (new i = 0; i < 4; i++)
	{
		if (q[i] != q[i] || floatabs(q[i]) > 10.0) return false;
	}
	return true;
}

public OnIncomingPacket(playerid, packetid, BitStream:bs)
{
	new bits;
	BS_GetNumberOfBitsUsed(bs, bits);

	switch (packetid)
	{
		case ID_PLAYER_SYNC:
		{
			if (bits < 552) return 0;
			new Float:pos[3], Float:quat[4], Float:vel[3];
			BS_IgnoreBits(bs, 8 + 16 + 16 + 16); // packetId + lr + ud + keys
			BS_ReadValue(bs, PR_FLOAT, pos[0], PR_FLOAT, pos[1], PR_FLOAT, pos[2],
				PR_FLOAT, quat[0], PR_FLOAT, quat[1], PR_FLOAT, quat[2], PR_FLOAT, quat[3]);
			BS_IgnoreBits(bs, 8 + 8 + 8 + 8); // health, armour, weapon/key, specialAction
			BS_ReadValue(bs, PR_FLOAT, vel[0], PR_FLOAT, vel[1], PR_FLOAT, vel[2]);
			BS_ResetReadPointer(bs);

			if (!AC_ValidCoord3(pos) || !AC_ValidFinite4(quat) || !AC_ValidCoord3(vel, 100.0))
				return 0;
		}
		case ID_VEHICLE_SYNC:
		{
			if (bits < 512) return 0;
			new vehId, Float:quat[4], Float:pos[3], Float:vel[3], Float:carHp, trailerId;
			BS_IgnoreBits(bs, 8);
			BS_ReadValue(bs, PR_UINT16, vehId);
			BS_IgnoreBits(bs, 16 + 16 + 16);
			BS_ReadValue(bs,
				PR_FLOAT, quat[0], PR_FLOAT, quat[1], PR_FLOAT, quat[2], PR_FLOAT, quat[3],
				PR_FLOAT, pos[0], PR_FLOAT, pos[1], PR_FLOAT, pos[2],
				PR_FLOAT, vel[0], PR_FLOAT, vel[1], PR_FLOAT, vel[2],
				PR_FLOAT, carHp);
			BS_IgnoreBits(bs, 8 + 8 + 8 + 8 + 8);
			BS_ReadValue(bs, PR_UINT16, trailerId);
			BS_ResetReadPointer(bs);

			if (vehId < 1 || vehId >= MAX_VEHICLES || trailerId == vehId) return 0;
			if (!AC_ValidCoord3(pos) || !AC_ValidFinite4(quat) || !AC_ValidCoord3(vel, 100.0)) return 0;
			if (carHp != carHp || carHp < 0.0 || carHp > 10000.0) return 0;
		}
		case ID_PASSENGER_SYNC:
		{
			if (bits < 200) return 0;
			new vehId, seatFlags, Float:pos[3];
			BS_IgnoreBits(bs, 8);
			BS_ReadValue(bs, PR_UINT16, vehId, PR_UINT8, seatFlags);
			BS_IgnoreBits(bs, 8 + 8 + 8 + 16 + 16 + 16);
			BS_ReadValue(bs, PR_FLOAT, pos[0], PR_FLOAT, pos[1], PR_FLOAT, pos[2]);
			BS_ResetReadPointer(bs);

			new seat = seatFlags & 0x3F;
			if (vehId < 1 || vehId >= MAX_VEHICLES || seat < 1 || seat > 7) return 0;
			if (!AC_ValidCoord3(pos)) return 0;
		}
		case ID_BULLET_SYNC:
		{
			if (bits < 328) return 0;
			new hitType, hitId, Float:orig[3], Float:hitPos[3], Float:off[3];
			BS_IgnoreBits(bs, 8);
			BS_ReadValue(bs, PR_UINT8, hitType, PR_UINT16, hitId,
				PR_FLOAT, orig[0], PR_FLOAT, orig[1], PR_FLOAT, orig[2],
				PR_FLOAT, hitPos[0], PR_FLOAT, hitPos[1], PR_FLOAT, hitPos[2],
				PR_FLOAT, off[0], PR_FLOAT, off[1], PR_FLOAT, off[2]);
			BS_ResetReadPointer(bs);

			if (hitType > 4) return 0;
			if (!AC_ValidCoord3(orig) || !AC_ValidCoord3(hitPos) || !AC_ValidCoord3(off)) return 0;
		}
	}
	return 1;
}
```

## 3. Incoming RPC Validation (`OnIncomingRPC`)

Filter critical RPCs before they invoke gamemode callbacks:

| RPC ID | Name | Common Exploit | Validation Rule |
|---|---|---|---|
| `62` | `RPC_DialogResponse` | Spoofed `dialogid` or oversized `inputtext` | Drop if `dialogId != sActiveDialog[playerid]` or `inputLen > 128` |
| `115` | `RPC_GiveTakeDamage` | `NaN` / negative / `99999.0` damage crasher or self-hit | Drop if `amount != amount \|\| amount <= 0.0 \|\| amount > 500.0 \|\| targetId == playerid` |
| `106` | `RPC_DamageVehicle` | Remote vehicle panel/tire destruction | Drop if `vehId < 1 \|\| vehId >= MAX_VEHICLES` or player is not driver/near `vehId` |

```pawn
const RPC_DIALOG_RESPONSE  = 62;
const RPC_DAMAGE_VEHICLE   = 106;
const RPC_GIVE_TAKE_DAMAGE = 115;

public OnIncomingRPC(playerid, rpcid, BitStream:bs)
{
	switch (rpcid)
	{
		case RPC_DIALOG_RESPONSE:
		{
			new dialogId, response, listitem, inputLen;
			BS_ReadValue(bs, PR_INT16, dialogId, PR_UINT8, response,
				PR_INT16, listitem, PR_UINT8, inputLen);
			BS_ResetReadPointer(bs);

			if (inputLen > 128) return 0;
			// Also compare dialogId against server-tracked sActiveDialog[playerid].
		}
		case RPC_GIVE_TAKE_DAMAGE:
		{
			new bool:giveOrTake, targetId, Float:amount, weaponId, bodyPart;
			BS_ReadValue(bs, PR_BOOL, giveOrTake, PR_UINT16, targetId,
				PR_FLOAT, amount, PR_UINT32, weaponId, PR_UINT32, bodyPart);
			BS_ResetReadPointer(bs);

			if (amount != amount || amount <= 0.0 || amount > 500.0) return 0;
			if (targetId == playerid || weaponId > 54) return 0;
		}
		case RPC_DAMAGE_VEHICLE:
		{
			new vehId;
			BS_ReadValue(bs, PR_UINT16, vehId);
			BS_ResetReadPointer(bs);

			if (vehId < 1 || vehId >= MAX_VEHICLES) return 0;
			new Float:vx, Float:vy, Float:vz;
			if (!GetVehiclePos(vehId, vx, vy, vz)) return 0;
			if (GetPlayerVehicleID(playerid) != vehId
				&& GetPlayerDistanceFromPoint(playerid, vx, vy, vz) > 35.0)
				return 0; // Remote vehicle damage exploit.
		}
	}
	return 1;
}
```

## 4. `nex-ac` Include Placement & `OnCheatDetected`

If your gamemode uses **Nex-AC** (`#include <nex-ac>`):

1. **Include order matters:** Place feature/plugin includes that Nex-AC integrates with (`<a_samp>` or `<open.mp>`, `<Pawn.RakNet>`, `<streamer>`, `<sscanf2>`, `<YSI_...>`) **before** `#include <nex-ac>`, and place your own gamemode modules **after** `#include <nex-ac>` so ALS native hooks (`GivePlayerWeapon`, `GivePlayerMoney`, `SetPlayerPos`, `ShowPlayerDialog`) intercept every call.
2. **Configuration macros go above `#include <nex-ac>`:** Define `#define NO_SUSPICION_LOGS`, `#define AC_USE_...`, and language macros before including `<nex-ac>`.
3. **Verify open.mp tag compatibility:** Upstream SA-MP `nex-ac` releases were written for `<a_samp>`; on open.mp, use an open.mp-compatible Nex-AC fork (or pair custom server-authoritative hooks + `Pawn.RakNet` above).
4. **Custom `OnCheatDetected` handler & whitelists:**

```pawn
// In your gamemode after #include <nex-ac>:
forward OnCheatDetected(playerid, const ip_address[], type, code);
public OnCheatDetected(playerid, const ip_address[], type, code)
{
	// Whitelist admins or custom scripted events (e.g. code 14 = airbreak/TP during admin spec).
	if (IsPlayerAdmin(playerid))
		return 1; // 1 = handled by gamemode; suppresses default Nex-AC kick/ban.

	if (type == 0) // Suspicion warning
	{
		// Log to database / alert online admins, or delay kick cleanly via SetTimerEx (PF701).
		printf("[AC] Suspect player %d (%s) code %d", playerid, ip_address, code);
		return 1;
	}
	return 0; // Let Nex-AC apply default handling if desired.
}
```
