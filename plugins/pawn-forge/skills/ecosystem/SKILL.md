---
name: ecosystem
description: Deep integration patterns for major SA-MP 0.3.7 and open.mp Pawn libraries: Pawn.RakNet BitStreams and packet/RPC hooks, YSI 5 modules (y_inline, y_dialog, y_va, y_bits, y_groups, y_master), Incognito's Streamer tuning/shapes/attachments, ColAndreas & MapAndreas physics/raycasting, samp-bcrypt vs bcrypt-samp, Pawn.CMD vs YCMD vs I-ZCMD, advanced sscanf2 specifiers, easyDialog, and mSelection. Use when integrating, configuring, or debugging third-party Pawn plugins, components, or YSI 5 subsystems.
license: MIT
compatibility: Optional Python 3.8+ for pawnforge CLI / MCP verification and pawncc 3.10.x compiler.
metadata:
  author: POORSAKEN2
  version: "0.2.0"
argument-hint: "[library or file]"
---

# SA-MP & open.mp Include Ecosystems

Use verified signatures, strict include ordering, and proper handle/memory hygiene when combining Pawn plugins, open.mp components, and YSI 5 libraries. Follow `pawn-standards` for baseline Pawn safety, `roleplay` for RP architecture, `anticheat` for combat/packet security, `audit` for codebase reviews, and `build` / `test` to compile and test.

## Tool Resolution Order

Use the first available tier for verification:
1. **Pawn Forge MCP** (if connected): `project_info`, `compile`, `lint`, `api_lookup`, `lookup`.
2. **Standalone CLI**: `pawnforge <cmd> --json` (or `python scripts/pawnforge_exec.py <cmd> --json`, `python -m pawnforge <cmd> --json`, or `uvx --from git+https://github.com/POORSAKEN2/pawn-forge pawnforge <cmd> --json`).
3. **Fallback**: inspect local `.inc` signatures, compile with `pawncc`, and suggest `pip install git+https://github.com/POORSAKEN2/pawn-forge.git`.

Always run `api_lookup` / `pawnforge api --project-dir .` before writing calls so exact header variants (e.g., `<samp_bcrypt>` vs `<bcrypt>`) and open.mp vs SA-MP tags match the project.

## Library Selection Matrix

| Problem | Recommended | Alternative / Notes |
|---|---|---|
| Raw RakNet packets & RPCs | `Pawn.RakNet` (`1.6.x-omp` on open.mp) | Replaces SA-MP `SKY` (unsupported on open.mp) |
| Modular hooks, iterators, timers, dialogs | `YSI 5` (`YSI_Coding`, `YSI_Data`, `YSI_Visual`) | `easyDialog` for lightweight named dialogs without YSI |
| Streamed objects, areas, pickups, labels | `Streamer` (`samp-streamer-plugin`) | Always prefer areas over `OnPlayerUpdate` distance polling (`PF802`) |
| 3D raycasting, LOS, custom map collision | `ColAndreas` (`ColAndreas.cadb`) | `MapAndreas` only for lightweight flat-terrain Z lookup |
| Password hashing | `Sreyas-Sreelal/samp-bcrypt` (`<samp_bcrypt>`) | `lassir/bcrypt-samp` (`<bcrypt>`); never MD5/Whirlpool/SHA256 |
| Command processing & argument parsing | `Pawn.CMD` + `sscanf2` | `YCMD` (`y_commands`) if using `y_groups`; `I-ZCMD` legacy only |
| Model preview grids | `PlayerTextDrawSetPreviewModel` (`textdraw`) | `mSelection` for legacy file-backed preview menus |

## Strict Include Ordering

Pawn ALS hooks and YSI integrations depend on include order. Always load headers in this order:

1. **Platform stdlib first:** `#include <open.mp>` (or `#include <a_samp>` on SA-MP 0.3.7).
2. **Plugin / component headers:** `<a_mysql>`, `<streamer>`, `<Pawn.RakNet>`, `<sscanf2>`, `<Pawn.CMD>`, `<colandreas>`, `<samp_bcrypt>`.
3. **YSI 5 compile macros & modules:** `#define YSI_NO_HEAP_MALLOC` / `#define YSI_NO_OPTIMISATION_MESSAGE`, then `<YSI_Coding\y_hooks>`, `<YSI_Coding\y_inline>`, `<YSI_Extra\y_inline_mysql>`, `<YSI_Visual\y_dialog>`, `<YSI_Data\y_iterate>`, etc.
4. **Anti-cheat ALS wrapper (if used):** `<nex-ac>` after plugins and YSI so its native hooks wrap everything below.
5. **Local gamemode modules last:** `#include "modules/accounts.pwn"`, `#include "modules/maps.pwn"`.

## SA-MP 0.3.7 Plugins vs open.mp Components

| Aspect | SA-MP 0.3.7 | open.mp |
|---|---|---|
| Binary folder & config | `plugins/` listed in `server.cfg` (`plugins streamer sscanf`) | `components/` (auto-loaded) for `-omp` builds; `legacy_plugins` in `config.json` only for non-component SA-MP plugins |
| `Pawn.RakNet` | `1.5.x` in `plugins/` | `1.6.x-omp` component in `components/` |
| `Pawn.CMD` / `sscanf2` | `plugins/` (`pawn-cmd`, `sscanf`) | `Pawn.CMD 3.4.0-omp+` and `sscanf 2.13.8+` in `components/` |
| `Streamer` / `ColAndreas` / `samp-bcrypt` | `plugins/` | Use open.mp component releases if available, or `legacy_plugins` in `config.json` with SA-MP compatibility enabled |
| Legacy plugins (`YSF`, `FCNPC`, `SKY`) | Loaded in `plugins/` | `YSF` mostly built into open.mp; `FCNPC` replaced by open.mp NPC component; `SKY` replaced by `Pawn.RakNet` |

## Reference Guides

Load only the reference matching the library you are working with:

| Ecosystem | Guide | Covers |
|---|---|---|
| `Pawn.RakNet` | [references/pawn-raknet.md](references/pawn-raknet.md) | `BS_New`/`BS_Delete` (`PF801`), `BS_ResetReadPointer`, `BS_ReadValue`/`BS_WriteValue`, `PR_SendPacket`/`PR_SendRPC`, `OnIncomingPacket`/`OnIncomingRPC`/`OnOutgoingRPC`, `IRPC:`/`IPacket:`, sync structs, 1.5.x vs `1.6.x-omp` |
| `YSI 5` | [references/ysi5-deep-dive.md](references/ysi5-deep-dive.md) | `y_inline` + `y_inline_mysql` + `y_inline_timers`, `y_dialog` (`Dialog_ShowCallback`), `y_va`, `y_bits` (`BitArray`), `y_groups`, `y_master`, `YSI_NO_HEAP_MALLOC` / `YSI_NO_OPTIMISATION_MESSAGE` |
| `Streamer` | [references/streamer-and-world.md](references/streamer-and-world.md) | `Streamer_SetMaxItems`, `Streamer_SetVisibleItems`, `Streamer_SetTickRate`, `Streamer_SetCellDistance`, polygon/circle/sphere/cuboid areas, attachments, `E_STREAMER_PLAYER_ID`, `E_STREAMER_EXTRA_ID`, `Streamer_UpdateEx` |
| `ColAndreas` & `MapAndreas` | [references/colandreas-and-physics.md](references/colandreas-and-physics.md) | `CA_Init`, `CA_RayCastLine`, `CA_RayCastLineEx`, `CA_FindZ_For2DCoord`, syncing `CA_CreateObject`/`CA_DestroyObject` with Streamer maps, `MapAndreas` fallback |
| Auth & Commands | [references/auth-and-commands.md](references/auth-and-commands.md) | `samp-bcrypt` vs `bcrypt-samp`, `Pawn.CMD` vs `YCMD` vs `I-ZCMD`, advanced `sscanf2` (`k<>`, `e<>`, `p<>`, `a<>`), `easyDialog`, `mSelection` |
