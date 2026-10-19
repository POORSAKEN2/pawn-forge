---
description: Security, stability and modernisation audit of a Pawn codebase (SA-MP / open.mp) - buffer overflows, format/sscanf mismatches, SQL injection, weak password hashing, leaked timers/TextDraws/caches, blocking queries, legacy libraries and invalid game IDs - with a prioritised, verified report. Use when asked to audit, review, harden or assess a gamemode or filterscript.
argument-hint: "[path]"
allowed-tools: mcp__plugin_pawn-forge_pawn__lint mcp__plugin_pawn-forge_pawn__lint_rules mcp__plugin_pawn-forge_pawn__project_info mcp__plugin_pawn-forge_pawn__api_lookup mcp__plugin_pawn-forge_pawn__lookup
---

# Audit a Pawn codebase

Scope: `$ARGUMENTS` (default: the working directory).

1. `project_info` for platform, libraries and layout.
2. `lint` the scope (third-party include dirs are skipped by default). For more than ~50 files, hand the work to
   the `pawn-forge:pawn-auditor` subagent and work from its report, to keep this conversation small.
3. **Verify before reporting.** Static analysis can be wrong: open the source line of every `error` and every
   `security` finding and confirm it is real. Drop false positives; note any rule that misfired.
4. Look beyond the linter for what it cannot see, in the files that matter most (account/login, admin, economy,
   dialogs):
   - `OnDialogResponse`: is `dialogid` checked, `listitem` bounded, `inputtext` length-checked before use?
   - Admin commands: is permission checked in every path (or centrally in `OnPlayerCommandReceived`)?
   - Money/items: can a client value (inputtext, params) reach `GivePlayerMoney` or an array index unchecked?
   - Passwords: stored hashed with bcrypt and a salt?
   - Disconnect cleanup: timers killed, per-player state reset, async query callbacks race-checked?
5. **Report** in this order, each item with `file:line`, why it matters (the concrete failure: crash, exploit,
   leak), and the fix:
   - **Critical**: memory-safety errors (PF101/102/104/105), SQL injection (PF201/202), exploitable logic.
   - **High**: leaks and blocking work (PF302-304, PF401-405, PF504), weak hashing (PF203), invalid IDs (PF6xx).
   - **Modernisation**: legacy libraries and patterns (PF3xx/PF5xx info), with the migration path.
   Group repeated instances of one rule ("PF103 in 14 places: ...") instead of listing each.
6. Offer to fix the Critical and High items, and to write the report to `PAWN_AUDIT.md` if the user wants to keep it.
   Do not start editing without the user's go-ahead.
