# YSI 5 Deep Dive (`y_inline`, `y_dialog`, `y_va`, `y_bits`, `y_groups`, `y_master`)

This guide extends `pawn-standards` (`references/ysi.md`, which covers `y_hooks`, `y_iterate`, basic `y_timers`, `y_commands`, and `y_testing`). Always use YSI 5 paths (`YSI_Coding\*`, `YSI_Data\*`, `YSI_Visual\*`, `YSI_Players\*`, `YSI_Server\*`, `YSI_Extra\*`), include YSI **after** `<open.mp>` / `<a_samp>` and C++ plugins (`<a_mysql>`, `<streamer>`), and compile with `-;+` (`pawn-build` / `pawnforge compile` enables this and normalizes backslash include paths on Linux/macOS).

## 1. Compile Macros (Define Before Including YSI)

```pawn
#include <open.mp>
#include <a_mysql>

#define YSI_NO_HEAP_MALLOC          // Avoid dynamic heap allocation inside YSI
#define YSI_NO_OPTIMISATION_MESSAGE // Suppress startup JIT/optimisation banner
#define YSI_NO_VERSION_CHECK        // Skip remote version check in isolated/CI environments

#include <YSI_Coding\y_hooks>
#include <YSI_Coding\y_inline>
#include <YSI_Extra\y_inline_mysql>
#include <YSI_Extra\y_inline_timers>
#include <YSI_Visual\y_dialog>
#include <YSI_Coding\y_va>
#include <YSI_Data\y_bits>
#include <YSI_Players\y_groups>
```

If code generation runs out of space on large gamemodes with many hooks or inlines, raise `#define CGEN_MEMORY 32768` (or `65536`) before the first YSI include.

## 2. `y_inline`, `y_inline_mysql`, and `y_inline_timers`

`y_inline` lets async callbacks capture local variables from the enclosing function, eliminating temporary global arrays and split `forward`/`public` boilerplate. **Still validate `IsPlayerConnected(playerid)`** inside async inlines because players can disconnect before a query or timer finishes.

```pawn
stock Account_LoadProfile(playerid, accountId)
{
	new query[128];
	mysql_format(gSQL, query, sizeof query,
		"SELECT `cash`, `admin_level` FROM `accounts` WHERE `id` = %d LIMIT 1", accountId);

	inline const OnLoaded()
	{
		if (!IsPlayerConnected(playerid)) return;
		if (cache_num_rows() > 0)
		{
			new cash, adminLevel;
			cache_get_value_name_int(0, "cash", cash);
			cache_get_value_name_int(0, "admin_level", adminLevel);
			SendClientMessage(playerid, -1, "Loaded account #%d ($%d).", accountId, cash);
			#pragma unused adminLevel
		}
	}
	MySQL_TQueryInline(gSQL, using inline OnLoaded, query);
}
```

With `y_inline_timers` (`#include <YSI_Extra\y_inline_timers>`), inline callbacks also work cleanly with delayed/paused execution (`wait_ms(ms)` inside an inline context or `SetTimerInline` / `SetTimerExInline`) alongside `y_timers` (`defer` / `repeat` / `stop`). Remember that `wait_ms` suspends only the current inline block; re-check player connection and state flags immediately after waking up.

## 3. `y_dialog`: Collision-Free Inline Dialogs

`Dialog_ShowCallback` removes the need for a global `enum` of dialog IDs and keeps response logic next to the menu presentation. Always validate `response`, `listitem` bounds, and `!inputtext[0]` / `isnull(inputtext)` (`PF702`) inside the handler:

```pawn
stock Shop_ShowMenu(playerid)
{
	inline const OnShopResponse(response, listitem, string:inputtext[])
	{
		#pragma unused inputtext
		if (!response) return;
		if (listitem < 0 || listitem >= 2) return;

		if (listitem == 0)
			SendClientMessage(playerid, -1, "Purchased water.");
		else
			SendClientMessage(playerid, -1, "Purchased medkit.");
	}

	Dialog_ShowCallback(playerid, using inline OnShopResponse, DIALOG_STYLE_LIST,
		"General Store", "Water ($5)\nMedkit ($50)", "Buy", "Close");
}
```

## 4. `y_va`: Variadic Argument Forwarding

Use `y_va` (`#include <YSI_Coding\y_va>`) when building logging, admin broadcast, or proximity-chat helpers that accept `{Float, _}:...` without duplicating `format` buffers at every call site:

```pawn
stock Admin_Broadcast(color, const fmat[], va_args<>)
{
	new msg[144];
	va_format(msg, sizeof msg, fmat, va_start<2>);
	foreach (new i : Player)
	{
		if (IsPlayerAdmin(i))
			SendClientMessage(i, color, "%s", msg); // Safe format literal (PF704/format guard)
	}
}
```

> `va_start<N>` takes the zero-based parameter index of `va_args<>` (`2` above because `color` is `0` and `fmat` is `1`).

## 5. `y_bits`: Compact Per-Player Bit Arrays

A standard `new bool:gMuted[MAX_PLAYERS];` allocates 1,000 cells (4,000 bytes). `BitArray` packs 32 boolean flags per cell (128 bytes for 1,000 players):

```pawn
new BitArray:gPlayerMuted<MAX_PLAYERS>;

stock Mute_Set(playerid, bool:muted)
{
	Bit_Set(gPlayerMuted, playerid, muted);
}

stock bool:Mute_Get(playerid)
{
	return Bit_Get(gPlayerMuted, playerid);
}

// Reset all flags in one call, or use Bit_Let(arr, id) / Bit_Vet(arr, id):
// Bit_SetAll(gPlayerMuted, false);
```

## 6. `y_groups`: Role & Faction Permissions

`y_groups` manages named sets of players and integrates directly with `y_commands` (`YCMD:`), Streamer items, and areas:

```pawn
new Group:gGroupAdmin;

stock Groups_Init()
{
	gGroupAdmin = Group_Create("Admin");
	Group_SetCommand(gGroupAdmin, YCMD:kick, true); // Only members of gGroupAdmin can run /kick
}

stock Groups_SetAdmin(playerid, bool:isAdmin)
{
	Group_SetPlayer(gGroupAdmin, playerid, isAdmin);
}
```

## 7. `y_master`: Multi-Script Coordination

`#include <YSI_Server\y_master>` lets a gamemode and filterscripts share `global` variables and `foreign` functions across `.amx` boundaries by electing one master script (`#define MASTER <id>`).

- **When to use `y_master`:** Only when your server architecture genuinely requires separate hot-reloadable `.amx` filterscripts sharing state with the gamemode.
- **When to avoid it:** For new open.mp or SA-MP gamemodes, prefer a single modular `.amx` built from `modules/*.inc` + `y_hooks`. Single-AMX modules have zero cross-VM call overhead and simpler CrashDetect stack traces.
