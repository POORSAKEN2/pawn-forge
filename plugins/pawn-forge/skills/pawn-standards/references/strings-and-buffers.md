# Strings and buffers

## Sizing

| Purpose | Size |
|---|---|
| Chat message sent to a client | 144 cells (longer text is cut off) |
| Chat / command text received from a client | 128 cells |
| Player name | `MAX_PLAYER_NAME + 1` (names are up to 24 characters via `SetPlayerName`) |
| Dialog caption / input box / body | 64 / 128 / 4096 |
| IP address | 16 |
| GameText / TextDraw string | 1024 (string length limit for TextDraws) |

Check `lookup kind=limit` for the full table from the open.mp docs.

## Safe patterns

```pawn
// Destination size always comes from the destination.
new msg[144];
format(msg, sizeof msg, "%s paid $%d", name, amount);

// open.mp: natives format directly; no intermediate buffer.
SendClientMessage(playerid, 0xFFFFFFFF, "%s paid $%d", name, amount);

// Copy a string: strcopy (open.mp / pawn stdlib) ...
strcopy(gPlayerTag[playerid], tag);
// ... or on old SA-MP includes:
gPlayerTag[playerid][0] = EOS;
strcat(gPlayerTag[playerid], tag, sizeof gPlayerTag[]);

// Read-only parameters are const.
stock bool:IsAdminName(const name[]) { ... }

// Enum string members: sizeof needs the full path.
enum E_PLAYER { E_PLAYER_NAME[MAX_PLAYER_NAME + 1], E_PLAYER_CASH }
new gPlayer[MAX_PLAYERS][E_PLAYER];
GetPlayerName(playerid, gPlayer[playerid][E_PLAYER_NAME], MAX_PLAYER_NAME + 1);
```

## Format specifiers

`%d`/`%i` integer, `%f` float (`%.2f` precision), `%s` string, `%c` char, `%x` hex, `%b` binary, `%%` literal,
`%q` SQLite-escaped string (0.3.7 R2+). `mysql_format` adds `%e` (MySQL-escaped string).
The number of specifiers must equal the number of arguments (`lint` rule PF104). `SetTimerEx`, `CallLocalFunction`
and `mysql_tquery` use a specifier *string* (`"ii"`) with one letter per argument.

## Never

- `format(dest, 256, ...)` on a smaller buffer, or `sizeof(other)` (PF101/PF102).
- `new string[256]` "just in case" in callbacks that run often.
- Passing `inputtext`/`params` as the format argument.
- Indexing arrays with unchecked client values (`listitem`, IDs from `params`).
