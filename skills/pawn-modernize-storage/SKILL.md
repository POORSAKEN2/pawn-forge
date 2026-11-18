---
name: pawn-modernize-storage
description: Replace dini, dfile, dudb, DOF2, or y_ini file storage in a Pawn gamemode with SQLite or MySQL R41 (schema design, escaped/threaded data access, one-time migration, bcrypt password re-hashing). Use when moving accounts or saves off .ini files, adding a database, or fixing file-based storage.
license: MIT
compatibility: Optional Python 3.8+ for pawnforge CLI / MCP verification and compiler tools.
metadata:
  author: POORSAKEN2
  version: "0.2.0"
---

# Move file storage to a database

Backend: `sqlite` or `mysql`. If unspecified, recommend and ask:
- **SQLite** (built into SA-MP and open.mp): zero setup, single server, one DB file in `scriptfiles/`.
- **MySQL R41**: multiple servers or shared web/panel access; requires plugin and DB server.

## Tool Resolution

1. **Pawn Forge MCP**: `project_info`, `lint`, `compile`, `api_lookup`.
2. **Standalone CLI**: `pawnforge <cmd> --json` (or `python scripts/pawnforge_exec.py <cmd> --json`, `python -m pawnforge <cmd> --json`, or `uvx --from git+https://github.com/POORSAKEN2/pawn-forge pawnforge <cmd> --json`).
3. **Fallback**: search `.ini` storage calls manually and compile with `pawncc`; suggest `pip install git+https://github.com/POORSAKEN2/pawn-forge.git`.

## Workflow

1. **Inventory.** Run `lint` (`rules: ["PF305"]`) / `pawnforge lint <path> --rules PF305 --json`, then grep for `dini_`, `dfile_`, `udb_`, `DOF2_`, `INI_`. Build a table: path pattern (e.g. `Users/%s.ini`), key, type, and read/write sites.
2. **Schema.** Design one table per entity (`players`, `houses`, `vehicles`...), `id INTEGER PRIMARY KEY`, a `UNIQUE` name column, and typed columns per key. Show `CREATE TABLE` statements to the user before editing code.
3. **Data-access module** (`includes/<entity>_db.inc` or project convention):
   - **SQLite**: `DB_Open` once at init, `DB_ExecuteQuery` with `%q` inside quotes for strings, read via `DB_GetFieldIntByName`/`DB_GetFieldStringByName`, and call `DB_FreeResultSet` on **every** result (use `db_*` on SA-MP 0.3.7).
   - **MySQL R41**: `mysql_tquery` + callback with a race-check counter, `mysql_format` with `%e`, never `mysql_query` in gameplay (see `pawn-standards` `references/mysql-r41.md`).
   - Load on connect, save on disconnect plus periodic saves for critical state; batch updates into one query.
4. **Passwords.** Legacy hashes (`udb_hash`, Whirlpool, etc.) cannot be converted directly. Store them with a `legacy` marker; on next successful login (verified with the old function), re-hash with `samp-bcrypt` and clear the marker.
5. **One-time migration.** Add a temporary filterscript or `migrate` RCON command that walks `.ini` files, inserts rows inside a `BEGIN`/`COMMIT` transaction, logs failures, and is removed afterwards. Advise backing up `scriptfiles/` first.
6. **Replace call sites**, drop `dini`/`y_ini` includes, then `compile` clean (`pawn-build`) and `lint` changed files (zero `PF201`/`PF202`/`PF304`/`PF305` remaining).
7. **Report**: schema, files changed, how to run migration, and rollback plan (untouched `.ini` files).
