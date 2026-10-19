# YSI 5 essentials

Include paths use the YSI 5 layout (`YSI_Coding`, `YSI_Data`, `YSI_Visual`...). YSI 4 paths (`YSI\y_hooks`) are
outdated. YSI requires semicolons (`-;+`), which the `compile` tool passes by default.

## y_hooks: one callback, many modules

```pawn
#include <YSI_Coding\y_hooks>

hook OnPlayerConnect(playerid)
{
	Speedo_CreatePlayer(playerid);
	return 1;
}
```

Every module hooks what it needs; the gamemode no longer owns a 2,000-line `OnPlayerConnect`.

## y_iterate (foreach)

```pawn
#include <YSI_Data\y_iterate>

foreach (new i : Player) { ... }              // connected players only

new Iterator:Houses<MAX_HOUSES>;
Iter_Add(Houses, houseid);
Iter_Remove(Houses, houseid);                 // inside a foreach over Houses use Iter_SafeRemove
new id = Iter_Free(Houses);                   // first free slot, or INVALID_ITERATOR_SLOT
Iter_Count(Houses); Iter_Contains(Houses, houseid);
```

## y_timers

```pawn
#include <YSI_Coding\y_timers>

task SaveAll[60000]() { ... }                 // global repeating task
ptask PlayerTick[1000](playerid) { ... }      // per-player, started/stopped automatically
timer RespawnLater[5000](playerid) { ... }
defer RespawnLater(playerid);                 // run once after the delay
new Timer:t = repeat RespawnLater(playerid);  // repeating; stop t; to cancel
```

## y_commands, y_inline, y_testing

- `YCMD:name(playerid, params[], help)` (see commands-and-input.md).
- `inline Name() { ... }` with `using inline Name` for callbacks that close over local variables
  (y_inline_mysql: `MySQL_TQueryInline`).
- Tests: `#define RUN_TESTS`, `#include <YSI_Core\y_testing>`, `@test() Name() { ASSERT_EQ(a, b); }`.
  The `run_server` tool runs them headlessly and reports `*** Tests: N, Checks: N, Fails: N`.

## Gotchas

- Include YSI after `<open.mp>` / `<a_samp>` and after plugin includes it integrates with (e.g. `a_mysql`).
- YSI's internal includes use backslash paths; `compile` normalises them automatically on Linux/macOS.
- First YSI compile is slow; that is normal.
