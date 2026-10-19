---
description: Migrate a SA-MP 0.3.7 gamemode or filterscript to open.mp - includes, renamed/deprecated natives, tagged constants, callback headers, plugins moving to components - then compile clean against the open.mp includes. Use when asked to port, upgrade or convert a SA-MP server or script to open.mp.
argument-hint: "[file.pwn | directory]"
allowed-tools: mcp__plugin_pawn-forge_pawn__migrate_openmp mcp__plugin_pawn-forge_pawn__compile mcp__plugin_pawn-forge_pawn__project_info mcp__plugin_pawn-forge_pawn__api_lookup mcp__plugin_pawn-forge_pawn__lint
---

# Migrate to open.mp

Target: `$ARGUMENTS` (default: the project's main script and its local includes).

1. **Survey.** `project_info`: confirm the current platform, list plugins (server.cfg / plugins/), libraries and
   includes. Note which files belong to the project (migrate those) and which are third-party (replace with
   open.mp-compatible releases instead of editing).
2. **Dry run** each project file with `migrate_openmp` (default `write: "none"`). Summarise per file: safe changes
   (applied mechanically) and manual items (need a decision).
3. **Apply** once the user agrees (or immediately if they asked you to migrate): `write: "in_place"` keeps a
   `<file>.samp.bak` backup. Use `write: "copy"` if the user wants the original untouched.
4. **Resolve manual items** by hand:
   - `GetPlayerPoolSize`/`GetVehiclePoolSize` loops: `i < MAX_PLAYERS` or `foreach (new i : Player)`.
     Watch for `<=` bounds that relied on the pool size.
   - Deprecated natives with no direct alias: use the replacement named in the item, checking its signature with
     `api_lookup`.
   - YSI 4 includes: update to YSI 5 paths.
5. **Compile** against open.mp's includes (`qawno/include` in the open.mp server package, found automatically) and
   iterate until clean, as in the `build` workflow. Remaining warning 213 means a literal where a tagged constant
   belongs; fix the call, never cast the tag away.
6. **Server side** (tell the user; do not edit their server config without asking):
   - `server.cfg` becomes `config.json` (`./omp-server --dump-config` converts it).
   - Component builds go in `components/`: Pawn.CMD (-omp release), Pawn.RakNet, sscanf 2.13.8+,
     discord-connector, sampvoice. Others stay in `plugins/` and are listed in `pawn.legacy_plugins`.
   - YSF is unnecessary; FCNPC is replaced by the NPC component; SKY by Pawn.RakNet.
7. **Verify**: `lint` the migrated files. If the user has an open.mp server directory, offer the `test` workflow to
   boot it headlessly.
8. **Report**: files changed, manual decisions taken, server-side steps left for the user.
