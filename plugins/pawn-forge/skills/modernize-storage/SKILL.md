---
description: Replace dini, dfile, dudb, DOF2 or y_ini file storage in a Pawn gamemode with SQLite or MySQL R41 - schema design, an escaped/threaded data-access module, a one-time data migration, and safe password re-hashing. Use when asked to move accounts or saves off .ini files, add a database, or fix file-based storage.
argument-hint: "[sqlite|mysql]"
allowed-tools: mcp__plugin_pawn-forge_pawn__lint mcp__plugin_pawn-forge_pawn__compile mcp__plugin_pawn-forge_pawn__project_info mcp__plugin_pawn-forge_pawn__api_lookup
---

# Move file storage to a database

Backend: `$ARGUMENTS` (`sqlite` or `mysql`). If not given, recommend and ask:
- **SQLite** (built into SA-MP and open.mp): zero setup, one server, one file in scriptfiles/.
- **MySQL R41**: several servers or a website/panel sharing the data; needs the plugin and a database server.

1. **Inventory.** `lint` with `rules: ["PF305"]`, then grep every storage call (`dini_`, `dfile_`, `udb_`, `DOF2_`,
   `INI_`). Build a table: file path pattern (e.g. `Users/%s.ini`), every key, its type, where it is read/written.
2. **Schema.** One table per entity (`players`, `houses`, `vehicles`...), an `id INTEGER PRIMARY KEY`, a `UNIQUE`
   name column, typed columns per key. Show the CREATE TABLE statements to the user before writing code.
3. **Data-access module** (`includes/<entity>_db.inc` or the project's convention):
   - SQLite: `DB_Open` once at init, `DB_ExecuteQuery` with `%q` inside quotes for strings (format arguments of
     `DB_ExecuteQuery` or `format`), read with `DB_GetFieldIntByName`/`DB_GetFieldStringByName`, and
     `DB_FreeResultSet` on every result. On SA-MP use the `db_*` equivalents.
   - MySQL R41: `mysql_tquery` + callback with a race-check counter, `mysql_format` with `%e`, never `mysql_query`
     in gameplay. Follow `pawn-standards` references/mysql-r41.md.
   - Load on connect, save on disconnect plus periodic saves for important state; batch updates into one query.
4. **Passwords.** Old hashes (udb_hash, Whirlpool...) cannot be converted. Store them with a `legacy` marker; on the
   next successful login (verified with the old function) re-hash with bcrypt and clear the marker.
5. **One-time migration.** A filterscript (or a `migrate` RCON command) that walks the old .ini files, inserts rows
   in a transaction (`BEGIN`/`COMMIT`), logs failures, and is removed afterwards. Tell the user to back up
   scriptfiles/ first.
6. **Replace call sites**, remove the dini/y_ini includes, then `compile` until clean and `lint` the changed files
   (no PF201/PF202/PF304/PF305 may remain).
7. **Report**: schema, files changed, how to run the migration, and the rollback plan (the untouched .ini files).
