---
description: Write and run headless tests for Pawn code on a local open.mp server - YSI y_testing unit tests (@test + ASSERT_*) for gameplay logic such as economy payouts, inventory limits and spawn rules, plus boot smoke tests that catch runtime errors. Use when asked to test, verify behaviour, add unit tests or check that a gamemode boots.
argument-hint: "[server-dir] [module or behaviour to test]"
allowed-tools: mcp__plugin_pawn-forge_pawn__compile mcp__plugin_pawn-forge_pawn__run_server mcp__plugin_pawn-forge_pawn__project_info mcp__plugin_pawn-forge_pawn__analyze_log mcp__plugin_pawn-forge_pawn__api_lookup
---

# Headless tests on open.mp

Arguments: `$ARGUMENTS`

Needs a local open.mp server directory (contains `omp-server` or `omp-server.exe`). If there is none, tell the user
to download the open.mp server package for their OS and extract it; do not download it yourself unasked. On 64-bit
Linux the server and compiler are 32-bit and need `libc6-i386 lib32stdc++6 lib32atomic1` (Debian/Ubuntu names).

## Unit tests (YSI y_testing)

1. Make game logic testable: pure functions (`Economy_Payout(level)`, `Inventory_CanAdd(playerid, item)`) separated
   from natives that need a connected player.
2. Create a test entry script `gamemodes/tests.pwn` (or `test/<module>_test.pwn` copied into gamemodes):
   ```pawn
   #define RUN_TESTS
   #include <open.mp>
   #include <YSI_Core\y_testing>
   #include "../includes/economy.inc"   // modules under test

   @test() PayoutScalesWithLevel()
   {
       ASSERT_EQ(Economy_Payout(1), 100);
       ASSERT_EQ(Economy_Payout(3), 300);
   }

   main() {}
   ```
   Available checks include `ASSERT`, `ASSERT_EQ`, `ASSERT_NE`, `ASSERT_LT`, `ASSERT_LE`, `ASSERT_GT`, `ASSERT_GE`,
   `ASSERT_TRUE`, `ASSERT_FALSE`, `ASSERT_ZE`, `ASSERT_NZ`, `ASSERT_NEAR`, `ASSERT_SAME`.
   Write a test for each rule the user cares about, including edge cases (0, negative, max values, invalid IDs).
3. `compile` the test script with `output: "alongside"` so `tests.amx` lands in gamemodes/.
4. `run_server` with `server_dir` and `script: "tests"`. It stops when y_testing prints its summary and returns
   `tests`, `fails`, `failed_tests` and the `FAIL:` assertion lines.
5. Fix failures in the code under test (not the test, unless the test is wrong), recompile, rerun until green.

## Boot smoke test

`compile` the gamemode with `output: "alongside"`, then `run_server` with `script` and a `stop_on` regex for a line
the gamemode prints when initialisation completes (or let it hit `timeout_s`). Check `script_errors`,
`runtime.incidents` and `missing_natives`. If `runtime_errors_detectable` is false, recommend adding crashdetect to
`pawn.legacy_plugins`: without it, out-of-bounds errors can be silent.

## Report

Tests run, pass/fail with the failing assertions, fixes made, and the command to rerun (`/pawn-forge:test`).
