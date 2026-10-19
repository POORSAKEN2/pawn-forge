# Commands, sscanf and client input

## Pawn.CMD (fast, plugin-based)

```pawn
#include <Pawn.CMD>
#include <sscanf2>

cmd:kick(playerid, params[])
{
	new target, reason[64];
	if (sscanf(params, "uS(No reason)[64]", target, reason))
		return SendClientMessage(playerid, -1, "Usage: /kick [player] [reason]");
	if (target == INVALID_PLAYER_ID)
		return SendClientMessage(playerid, -1, "Player not found.");
	Kick(target);
	return 1;
}
alias:kick("k")                 // no semicolon: the macro expands to a function
flags:kick(CMD_ADMIN)           // CMD_ADMIN is your own bit flag, e.g. enum (<<= 1) { CMD_USER = 1, CMD_ADMIN }
```

Hooks provided by Pawn.CMD: `OnPlayerCommandReceived(playerid, cmd[], params[], flags)` (return 0 to block) and
`OnPlayerCommandPerformed(playerid, cmd[], params[], result, flags)`. Check `flags` in
`OnPlayerCommandReceived` for permissions instead of repeating checks in every command.
On open.mp, Pawn.CMD is a component: use the -omp release in `components/`.

## YSI y_commands

```pawn
#include <YSI_Visual\y_commands>

YCMD:heal(playerid, params[], help)
{
	if (help) return SendClientMessage(playerid, -1, "Restores your health.");
	SetPlayerHealth(playerid, 100.0);
	return 1;
}
```

## sscanf2 essentials

| Specifier | Meaning |
|---|---|
| `i` / `d` | integer |
| `f` | float |
| `s[n]` | string of at most n cells (size is mandatory) |
| `u` | player name or ID (`INVALID_PLAYER_ID` if no match) |
| `c` | character |
| `I(5)`, `S(default)[n]`, `U(-1)` | optional with default |
| `p<,>` | change delimiter |
| `a<i>[5]` | array |
| `e<...>` | fill an enum |

`sscanf` returns 0 on success. Every string specifier needs `[size]` matching the destination (lint PF105).

## Dialogs

- Name IDs with an enum: `enum { DIALOG_NONE, DIALOG_LOGIN, DIALOG_REGISTER };`
- In `OnDialogResponse`, check `dialogid`, then `response`, then validate `listitem` against your list size and
  `strlen(inputtext)` against your buffer before use. Clients can send responses for dialogs you never showed.
- Return 1 when you handled the dialog; returning 0 lets other scripts handle it.
