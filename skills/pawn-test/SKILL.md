---
name: pawn-test
description: Write and run headless tests for Pawn code on a local open.mp server using YSI y_testing unit tests (@test + ASSERT_*) and boot smoke tests that catch runtime errors. Use when asked to test, verify gameplay behaviour, add unit tests, or check that a gamemode boots cleanly.
license: MIT
compatibility: Optional Python 3.8+ for pawnforge CLI / MCP tools, pawncc, and a local open.mp server binary.
metadata:
  author: POORSAKEN2
  version: "0.2.0"
---

# Headless tests on open.mp

Requires a local open.mp server directory (`omp-server` or `omp-server.exe`). If none exists, instruct the user to download and extract the open.mp server package for their OS; do not download it unasked. On 64-bit Linux, 32-bit binaries need `libc6-i386 lib32stdc++6 lib32atomic1`.

## Tool Resolution

1. **Pawn Forge MCP**: `project_info`, `compile`, `run_server`, `analyze_log`, `api_lookup`.
2. **Standalone CLI**: `pawnforge <cmd> --json` (or `python scripts/pawnforge_exec.py <cmd> --json`, `python -m pawnforge <cmd> --json`, or `uvx --from git+https://github.com/POORSAKEN2/pawn-forge pawnforge <cmd> --json`).
3. **Fallback**: compile with `pawncc` and run `omp-server` manually; suggest `pip install git+https://github.com/POORSAKEN2/pawn-forge.git`.

## Unit tests (YSI y_testing)

1. **Isolate pure logic** (`Economy_Payout(level)`, `Inventory_CanAdd(playerid, item)`) from natives requiring a connected player.
2. **Create `gamemodes/tests.pwn`** (or `test/<module>_test.pwn` compiled into `gamemodes/`):
   ```pawn
   #define RUN_TESTS
   #include <open.mp>
   #include <YSI_Core\y_testing>
   #include "../includes/economy.inc"

   @test() PayoutScalesWithLevel()
   {
       ASSERT_EQ(Economy_Payout(1), 100);
       ASSERT_EQ(Economy_Payout(3), 300);
   }

   main() {}
   ```
   Macros: `ASSERT`, `ASSERT_EQ`, `ASSERT_NE`, `ASSERT_LT`, `ASSERT_LE`, `ASSERT_GT`, `ASSERT_GE`, `ASSERT_TRUE`, `ASSERT_FALSE`, `ASSERT_ZE`, `ASSERT_NZ`, `ASSERT_NEAR`, `ASSERT_SAME`. Cover edge cases (`0`, negatives, max values, invalid IDs).
3. **Compile** with `output: "alongside"` / `pawnforge compile gamemodes/tests.pwn --output alongside --json` so `tests.amx` lands in `gamemodes/`.
4. **Run headlessly** via `run_server` (`server_dir`, `script: "tests"`) / `pawnforge run-server <dir> --script tests --json`; stops on the `y_testing` summary and returns `tests`, `fails`, `failed_tests`, and `FAIL:` lines.
5. **Fix** bugs in the code under test, recompile, and rerun until green.

## Boot smoke test

Compile the gamemode (`--output alongside`), then run `run_server` / `pawnforge run-server <dir> --script <name> --stop-on <regex> --json` (or `--timeout <sec>`). Check `script_errors`, `runtime.incidents`, and `missing_natives`. If `runtime_errors_detectable` is false, recommend adding CrashDetect to `pawn.legacy_plugins` so out-of-bounds errors are not silent.

## Report

Tests run, pass/fail counts with failing assertions, fixes made, and rerun command (`pawnforge run-server <dir> --script tests` or `pawn-test`).
