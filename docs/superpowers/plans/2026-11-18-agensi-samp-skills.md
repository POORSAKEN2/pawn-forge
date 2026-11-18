# Pawn Forge Agensi Multi-Agent Skills & SA-MP Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repackage Pawn Forge into a portable, Agensi-ready suite of AI agent skills backed by a zero-dependency standalone Python CLI, while expanding SA-MP scripting coverage and static analysis for roleplay systems, anti-cheat, and include ecosystems.

**Architecture:** Canonical `agentskills.io`-compliant skills live at root `skills/pawn-*` for `npx skills add` and Agensi compatibility across 20+ coding agents, synced via a deterministic mapping script (`sync_skills.py`) into `plugins/pawn-forge/skills/` to preserve backward-compatible Claude Code slash commands. All MCP tools are exposed 1:1 through a stdlib-only `pawnforge` CLI packaged via `pyproject.toml` so non-MCP agents execute deterministic compilation, linting, and lookups via shell fallback.

**Tech Stack:** Python 3.8+ (standard library only), PEP 621 / `setuptools` packaging (`pyproject.toml`), Agent Skills (`SKILL.md` + `references/` + `scripts/`), Pawn (SA-MP 0.3.7 & open.mp), `unittest`.

**Spec:** `docs/superpowers/specs/2026-11-18-agensi-samp-skills-design.md`

---

## Global Constraints

- **Python 3.8+ Standard Library Only:** `pawnforge`, `pawn_mcp.py`, CLI commands, and helper scripts must require zero third-party `pip` packages.
- **Cross-Platform Execution:** Must operate reliably on Windows, Linux, and macOS (no Git symlinks; handle path separators and YSI backslash include normalization).
- **Agent Skills (`agentskills.io` / Agensi) Specification:** Every skill directory contains `SKILL.md` with YAML frontmatter `name` (1-64 chars, `^[a-z0-9-]+$`, matching directory name) and `description` (1-1024 chars stating what it does and when to trigger), using progressive disclosure (`SKILL.md` < ~120 lines + `references/`).
- **Zero Duplicate 900KB JSON Bundles:** Keep `server/data/*.json` inside the Python package rather than duplicating JSON files into all 11 skill folders.
- **Conservative Linting & Verified Signatures:** New lint rules must stay quiet on idiomatic clean code; every Pawn signature and constant in references must match upstream headers.
- **Backward Compatibility:** All 46 existing unit tests and `.claude-plugin/marketplace.json` / `plugins/pawn-forge/` must continue functioning.

## Review Focus

1. **CLI `--code -` / `--text -` stdin handling & missing paths (`cli.py`):** Passing `--code -` or `--text -` reads stdin without treating `-` as a filename; non-existent paths return structured JSON `ok: false` and exit code `1` rather than an uncaught traceback. *(Covered in Task 3 tests)*
2. **Modular or include-only SA-MP project detection (`project.py` / `api.py`):** A project with no `gamemodes/*.pwn` (e.g., `includes/core.inc` containing `#include <a_samp>`) still resolves platform `"sa-mp"` instead of `"unknown"`, filtering out `open.mp` stdlib symbols and `openmp_deprecation`. *(Covered in Task 1 tests)*
3. **False positives in anti-cheat lint rules (`lint.py`):** Delayed kicks (`SendClientMessage` -> `SetTimerEx`/`defer`), guarded `strcmp` checks (`if (isnull(inputtext))` / `if (!inputtext[0])` before `strcmp`), bounds-checked combat callbacks, and `BS_New()` paired with `BS_Delete()` must remain quiet. *(Covered in Task 4 tests)*
4. **Standalone skill bootstrapper outside repo (`pawnforge_exec.py`):** When `npx skills add` copies an isolated skill directory into `~/.cursor/skills/pawn-build/` with no parent `pawn-forge` repo, `scripts/pawnforge_exec.py` resolves `pawnforge` on `PATH`/`python -m`/global plugin caches and outputs clean JSON install guidance if absent instead of crashing. *(Covered in Task 5 tests)*
5. **`api_lookup` backward compatibility (`api.py`):** With both `open.mp` and `samp-stdlib` indexed, `api_lookup(name="GetPlayerPoolSize")` without `project_dir` or `library` still returns `open.mp` with `openmp_deprecation` (never hidden or duplicated by `samp-stdlib`). *(Covered in Task 1 & Task 2 tests)*

---

## Task 1: Project Detection & `api_lookup` Platform Filtering

**Files:**
- Modify: `plugins/pawn-forge/server/pawnforge/project.py:126-172`
- Modify: `plugins/pawn-forge/server/pawnforge/api.py:62-101`
- Modify: `plugins/pawn-forge/server/pawnforge/tools.py:134-142`
- Test: `plugins/pawn-forge/tests/test_tools.py`

**Interfaces:**
- Produces in `project.py`: `collect_project_includes(root: Path, main_script: str | None) -> list[str]` and extended `project_info(project_dir: str) -> dict` (detecting `pawn.raknet`, `colandreas`, `mapandreas`, `samp-bcrypt`, `nex-ac`, `easydialog`, `mselection` in `libraries_detected`).
- Produces in `api.py`: `api_lookup(name: str | None = None, query: str | None = None, library: str | None = None, project_dir: str | None = None, limit: int = 10, platform: str = "auto") -> dict`.

- [ ] **Step 1: Write the failing tests in `plugins/pawn-forge/tests/test_tools.py`**

Add a `ProjectAndPlatformApiTest(unittest.TestCase)` class testing modular SA-MP include detection, new library detections, and `api_lookup` platform filtering (`open.mp` default vs `sa-mp` filtering):

```python
class ProjectAndPlatformApiTest(unittest.TestCase):
    def test_detects_new_libraries_and_modular_samp_platform(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "includes").mkdir()
            Path(d, "includes", "core.inc").write_text(
                "#include <a_samp>\n#include <Pawn.RakNet>\n#include <samp_bcrypt>\n"
                "#include <colandreas>\n#include <nex-ac>\n#include <easyDialog>\n"
            )
            info = project.project_info(d)
            self.assertEqual(info["platform"], "sa-mp")
            for lib in ("pawn.raknet", "samp-bcrypt", "colandreas", "nex-ac", "easydialog"):
                self.assertIn(lib, info["libraries_detected"])

    def test_api_lookup_platform_filtering_and_collision_handling(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "include").mkdir()
            Path(d, "gamemodes").mkdir()
            Path(d, "gamemodes", "gm.pwn").write_text("#include <a_samp>\nmain(){}\n")
            fake_bundled = [
                {"name": "TextDrawColour", "library": "open.mp", "signature": "native TextDrawColour(Text:text, colour)"},
                {"name": "GetPlayerPoolSize", "library": "open.mp", "signature": "native GetPlayerPoolSize()"},
                {"name": "GetPlayerPoolSize", "library": "samp-stdlib", "signature": "native GetPlayerPoolSize()"},
            ]
            with unittest.mock.patch("pawnforge.api.data.load", side_effect=lambda k: fake_bundled if k == "natives" else ([] if k == "callbacks" else {"GetPlayerPoolSize": {"replacement": "MAX_PLAYERS"}} if k == "omp_deprecations" else {})):
                default_res = api.api_lookup(name="GetPlayerPoolSize")
                self.assertEqual([r["library"] for r in default_res["results"]], ["open.mp"])
                self.assertIn("openmp_deprecation", default_res)

                samp_res = api.api_lookup(name="GetPlayerPoolSize", project_dir=d)
                self.assertEqual([r["library"] for r in samp_res["results"]], ["samp-stdlib"])
                self.assertNotIn("openmp_deprecation", samp_res)

                explicit_samp = api.api_lookup(query="TextDrawColour", platform="sa-mp")
                self.assertEqual(explicit_samp["count"], 0)
```

- [ ] **Step 2: Run the failing tests**

Run: `python -m unittest discover -s plugins/pawn-forge/tests -t plugins/pawn-forge/tests -p test_tools.py -v`
Expected: FAIL (`TypeError: api_lookup() got an unexpected keyword argument 'platform'` and `platform == 'unknown'` instead of `'sa-mp'`).

- [ ] **Step 3: Implement `collect_project_includes` and new library checks in `plugins/pawn-forge/server/pawnforge/project.py`**

Add `collect_project_includes(root: Path, main_script: str | None) -> list[str]` returning de-duplicated `#include` names from `main_script` plus (when `main_script` lacks platform headers or doesn't exist) local `.pwn`/`.inc` files under `gamemodes`, `filterscripts`, `src`, `include`, `includes`, `inc` (excluding `qawno/`, `pawno/`, `dependencies/`). Extend `libs` in `project_info` to detect `pawn.raknet`, `colandreas`, `mapandreas`, `samp-bcrypt` (`samp_bcrypt` or `bcrypt`), `nex-ac` (`nex-ac` or `nex_ac`), `easydialog`, and `mselection`.

- [ ] **Step 4: Implement `platform` resolution and stdlib filtering in `plugins/pawn-forge/server/pawnforge/api.py` and `tools.py`**

Normalize `platform` (`"auto"`, `"open.mp"`/`"openmp"`, `"sa-mp"`/`"samp"`). When `platform == "auto"`, inspect `project.project_info(project_dir)["platform"]` if `project_dir` is given (`"sa-mp"` -> `"sa-mp"`, else `"open.mp"`). When `library` is None, drop `samp-stdlib` if resolved platform is `"open.mp"`, or drop `open.mp` if resolved platform is `"sa-mp"`. Suppress `openmp_deprecation` when resolved platform is `"sa-mp"` or `library` is `"samp-stdlib"`. Add `"platform": {"type": "string", "enum": ["auto", "open.mp", "sa-mp", "openmp", "samp"]}` to `api_lookup` schema in `tools.py`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m unittest discover -s plugins/pawn-forge/tests -t plugins/pawn-forge/tests -v`
Expected: PASS (all `test_tools.py` and `test_lint.py` tests pass).

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/specs/2026-11-18-agensi-samp-skills-design.md docs/superpowers/plans/2026-11-18-agensi-samp-skills.md plugins/pawn-forge/server/pawnforge/project.py plugins/pawn-forge/server/pawnforge/api.py plugins/pawn-forge/server/pawnforge/tools.py plugins/pawn-forge/tests/test_tools.py
git commit -m "feat: add SA-MP platform filtering to api_lookup and expand library detection"
```

---

## Task 2: Reference Data Expansion & Regeneration (`build_data.py` + `server/data/*.json`)

**Files:**
- Modify: `plugins/pawn-forge/tools/build_data.py:295-345`
- Regenerate: `plugins/pawn-forge/server/data/natives.json`, `callbacks.json`, `sources.json`
- Test: `plugins/pawn-forge/tests/test_tools.py`

**Interfaces:**
- Consumes: `build_data.py` `scan_includes(paths, library, root)`
- Produces: regenerated `natives.json`, `callbacks.json`, `sources.json` containing `samp-stdlib`, `pawn.raknet`, `samp-bcrypt`, and `colandreas` alongside existing libraries.

- [ ] **Step 1: Write the failing tests in `plugins/pawn-forge/tests/test_tools.py`**

Add test assertions verifying that `api.api_lookup` resolves real bundled entries for `Pawn.RakNet` (`BS_New`), `samp-bcrypt` (`bcrypt_hash`), `ColAndreas` (`CA_RayCastLine`), and `samp-stdlib` (`SendClientMessage` with `platform="sa-mp"`), and that `sources.json` documents the new upstream repositories:

```python
    def test_bundled_samp_ecosystem_apis_present(self):
        self.assertTrue(api.api_lookup(name="BS_New")["found"])
        self.assertTrue(api.api_lookup(name="bcrypt_hash")["found"])
        self.assertTrue(api.api_lookup(name="CA_RayCastLine")["found"])
        samp = api.api_lookup(name="SendClientMessage", platform="sa-mp")
        self.assertTrue(samp["found"])
        self.assertEqual(samp["results"][0]["library"], "samp-stdlib")
        self.assertIn("samp-stdlib", data.load("sources"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest discover -s plugins/pawn-forge/tests -t plugins/pawn-forge/tests -p test_tools.py -k test_bundled_samp_ecosystem_apis_present -v`
Expected: FAIL (`AssertionError: False is not true` for `BS_New`, `bcrypt_hash`, `CA_RayCastLine`).

- [ ] **Step 3: Update `plugins/pawn-forge/tools/build_data.py` to support optional/new sources**

Add candidate header discovery in `main()` for:
- `"samp-stdlib"`: `sorted((src / "samp-stdlib").glob("a_*.inc"))`
- `"pawn.raknet"`: `[src / "Pawn.RakNet" / "Pawn.RakNet.inc", src / "Pawn.RakNet" / "include" / "Pawn.RakNet.inc"]`
- `"samp-bcrypt"`: `[src / "samp-bcrypt" / "samp_bcrypt.inc", src / "samp-bcrypt" / "include" / "samp_bcrypt.inc"]`
- `"colandreas"`: `[src / "ColAndreas" / "Server" / "include" / "colandreas.inc", src / "ColAndreas" / "include" / "colandreas.inc"]`
Skip any new optional source directory cleanly if absent from `--sources`, and record git SHAs in `sources.json` for every source directory present.

- [ ] **Step 4: Clone upstream headers into a temporary folder and regenerate `server/data/`**

Clone the original 6 repos at their pinned commits in `sources.json` plus `pawn-lang/samp-stdlib`, `katursis/Pawn.RakNet`, `Sreyas-Sreelal/samp-bcrypt`, and `Pottus/ColAndreas` into a temporary directory outside the repo, run `python plugins/pawn-forge/tools/build_data.py --sources <temp>`, verify `natives.json`/`callbacks.json`/`sources.json` updated cleanly, and delete the temp directory.

- [ ] **Step 5: Run tests to verify all `DataTest`, `LookupTest`, and `ApiTest` assertions pass**

Run: `python -m unittest discover -s plugins/pawn-forge/tests -t plugins/pawn-forge/tests -v`
Expected: PASS (all unit tests pass, `test_bundled_samp_ecosystem_apis_present` passes).

- [ ] **Step 6: Commit**

```bash
git add plugins/pawn-forge/tools/build_data.py plugins/pawn-forge/server/data/ plugins/pawn-forge/tests/test_tools.py
git commit -m "feat: index Pawn.RakNet, samp-bcrypt, ColAndreas, and samp-stdlib in reference data"
```

---

## Task 3: Standalone Zero-Dependency CLI & Package Entry Points

**Files:**
- Create: `pyproject.toml`
- Modify: `plugins/pawn-forge/server/pawnforge/data.py:8-15`
- Create: `plugins/pawn-forge/server/pawnforge/cli.py`
- Create: `plugins/pawn-forge/server/pawnforge/__main__.py`
- Create: `plugins/pawn-forge/server/pawnforge/mcp_entry.py`
- Modify: `plugins/pawn-forge/server/pawn_mcp.py` (delegate `main` cleanly or stay compatible)
- Test: `plugins/pawn-forge/tests/test_cli.py`

**Interfaces:**
- Consumes: `pawnforge.tools.call_tool(name: str, arguments: dict) -> dict`
- Produces:
  - `pyproject.toml` exposing `pawnforge = "pawnforge.cli:main"` and `pawnforge-mcp = "pawnforge.mcp_entry:main"`, mapping `pawnforge._data` -> `plugins/pawn-forge/server/data`.
  - `pawnforge.cli.main(argv: list[str] | None = None) -> int` supporting subcommands `info`, `compile`, `install-compiler`, `lint`, `lint-rules`, `analyze-log`, `lookup`, `api`, `migrate`, `textdraw`, `run-server`, plus `--json` and `--strict`.

- [ ] **Step 1: Write the failing test `plugins/pawn-forge/tests/test_cli.py`**

```python
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import FIXTURES, PLUGIN


class CliTest(unittest.TestCase):
    def run_cli(self, args, stdin_text=None):
        env = dict(os.environ, PYTHONPATH=str(PLUGIN / "server"))
        return subprocess.run(
            [sys.executable, "-m", "pawnforge", *args],
            input=stdin_text, capture_output=True, text=True, timeout=60, env=env,
        )

    def test_lint_stdin_and_json_parity(self):
        code = 'f(){ new a[8]; format(a, 99, "x"); }'
        r = self.run_cli(["lint", "--code", "-", "--json"], stdin_text=code)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertTrue(payload["ok"])
        self.assertIn("PF102", payload["by_rule"])

    def test_lint_strict_nonzero_on_error(self):
        r = self.run_cli(["lint", "--code", 'f(){ new a[8]; format(a, 99, "x"); }', "--strict", "--json"])
        self.assertEqual(r.returncode, 1)
        self.assertIn("PF102", json.loads(r.stdout)["by_rule"])

    def test_subcommands_json_and_missing_path(self):
        for cmd in (
            ["lookup", "vehicle", "infernus", "--json"],
            ["api", "--name", "mysql_tquery", "--json"],
            ["lint-rules", "--json"],
            ["info", str(FIXTURES), "--json"],
            ["analyze-log", str(FIXTURES / "server_log.txt"), "--source-root", str(FIXTURES / "src"), "--json"],
            ["migrate", str(FIXTURES / "legacy_samp.pwn"), "--write", "none", "--json"],
            ["textdraw", str(FIXTURES / "td_export.pwn"), "--prefix", "Speedo", "--json"],
        ):
            with self.subTest(cmd=cmd[0]):
                r = self.run_cli(cmd)
                self.assertEqual(r.returncode, 0, r.stderr)
                json.loads(r.stdout)
        missing = self.run_cli(["lint", "/nonexistent/path/gm.pwn", "--json"])
        self.assertEqual(missing.returncode, 1)
        self.assertFalse(json.loads(missing.stdout)["ok"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest discover -s plugins/pawn-forge/tests -t plugins/pawn-forge/tests -p test_cli.py -v`
Expected: FAIL (`No module named pawnforge.__main__`).

- [ ] **Step 3: Update `data.py` packaged data fallback and create `pyproject.toml`, `cli.py`, `__main__.py`, `mcp_entry.py`**

- In `plugins/pawn-forge/server/pawnforge/data.py`: resolve `_PKG_DATA = Path(__file__).resolve().parent / "_data"`, using `_PKG_DATA` when `(_PKG_DATA / "sources.json").exists()`, else `Path(__file__).resolve().parent.parent / "data"`.
- In `pyproject.toml`: configure PEP 621 `name = "pawn-forge"`, `requires-python = ">=3.8"`, `dependencies = []`, `package-dir = {"pawnforge": "plugins/pawn-forge/server/pawnforge", "pawnforge._data": "plugins/pawn-forge/server/data"}`, `[tool.setuptools.package-data] "pawnforge._data" = ["*.json"]`, `[project.scripts] pawnforge = "pawnforge.cli:main"` and `pawnforge-mcp = "pawnforge.mcp_entry:main"`.
- In `plugins/pawn-forge/server/pawnforge/cli.py`: implement `main(argv: list[str] | None = None) -> int` using a shared `--json` parent parser across all 11 subcommands (`info`, `compile`, `install-compiler`, `lint`, `lint-rules`, `analyze-log`, `lookup`, `api`, `migrate`, `textdraw`, `run-server`), reading `sys.stdin.read()` when `--code -` or `--text -` is passed, dispatching through `tools.call_tool`, formatting compact human-readable text when `--json` is omitted, returning exit `1` when `result.get("ok") is False` (or when `--strict` is set and `lint` has errors or `compile` has `ok: False`).
- Create `__main__.py` (`raise SystemExit(main())`) and `mcp_entry.py` (contains or delegates to the stdio MCP loop, with `server/pawn_mcp.py` still executable directly via `python server/pawn_mcp.py`).

- [ ] **Step 4: Run `test_cli.py` and full test suite to verify**

Run: `python -m unittest discover -s plugins/pawn-forge/tests -t plugins/pawn-forge/tests -v`
Expected: PASS (all CLI and MCP tests pass).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml plugins/pawn-forge/server/pawnforge/data.py plugins/pawn-forge/server/pawnforge/cli.py plugins/pawn-forge/server/pawnforge/__main__.py plugins/pawn-forge/server/pawnforge/mcp_entry.py plugins/pawn-forge/server/pawn_mcp.py plugins/pawn-forge/tests/test_cli.py
git commit -m "feat: add zero-dependency pawnforge CLI and PEP 621 package configuration"
```

---

## Task 4: Anti-Cheat, Security & Ecosystem Lint Rules (`PF701`–`PF802`)

**Files:**
- Modify: `plugins/pawn-forge/server/pawnforge/lint.py`
- Modify: `plugins/pawn-forge/tests/fixtures/legacy_bad.pwn`
- Modify: `plugins/pawn-forge/tests/test_lint.py`

**Interfaces:**
- Produces in `lint.py`: rules `PF701`, `PF702`, `PF703`, `PF704`, `PF801`, `PF802` registered in `RULES` and checked via `Linter.check_*` methods.

- [ ] **Step 1: Write the failing tests in `plugins/pawn-forge/tests/test_lint.py` and update `legacy_bad.pwn`**

Add annotated defect lines to `tests/fixtures/legacy_bad.pwn` for `PF701`–`PF704` and `PF801`–`PF802`, and add unit tests in `test_lint.py` verifying both positive detection and clean-code/false-positive immunity:

```python
    def test_anticheat_and_ecosystem_rules_and_false_positive_guards(self):
        # PF701: immediate Kick after SendClientMessage fires; timer-delayed kick stays quiet
        bad_kick = 'f(p){ SendClientMessage(p, -1, "Bye"); Kick(p); }'
        good_kick = 'f(p){ SendClientMessage(p, -1, "Bye"); SetTimerEx("DelayedKick", 200, false, "i", p); }'
        self.assertIn("PF701", self.rules(bad_kick))
        self.assertEqual(self.rules(good_kick), [])

        # PF702: unguarded strcmp on inputtext fires; isnull/inputtext[0]/strlen guard stays quiet
        bad_cmp = 'public OnDialogResponse(p,d,r,l,inputtext[]){ if(!strcmp(inputtext, "pw")) return 1; return 0; }'
        good_cmp = 'public OnDialogResponse(p,d,r,l,inputtext[]){ if(isnull(inputtext)) return 0; if(!strcmp(inputtext, "pw")) return 1; return 0; }'
        self.assertIn("PF702", self.rules(bad_cmp))
        self.assertEqual(self.rules(good_cmp), [])

        # PF703: unguarded weaponid/damagedid array index in OnPlayerWeaponShot/OnPlayerGiveDamage
        bad_dmg = 'new gWep[50]; public OnPlayerWeaponShot(p,w,h,hi,Float:x,Float:y,Float:z){ return gWep[w]; }'
        good_dmg = 'new gWep[50]; public OnPlayerWeaponShot(p,w,h,hi,Float:x,Float:y,Float:z){ if(w < 0 || w >= sizeof gWep) return 0; return gWep[w]; }'
        self.assertIn("PF703", self.rules(bad_dmg))
        self.assertEqual(self.rules(good_dmg), [])

        # PF704: RCON format with %s
        self.assertIn("PF704", self.rules('f(p[]){ new c[64]; format(c, sizeof c, "kick %s", p); SendRconCommand(c); }'))

        # PF801: BS_New without BS_Delete; paired BS_Delete stays quiet
        self.assertIn("PF801", self.rules('f(p){ new BitStream:bs = BS_New(); BS_WriteValue(bs, PR_INT32, p); }'))
        self.assertEqual(self.rules('f(p){ new BitStream:bs = BS_New(); BS_WriteValue(bs, PR_INT32, p); BS_Delete(bs); }'), [])

        # PF802: IsPlayerInRangeOfPoint inside OnPlayerUpdate
        self.assertIn("PF802", self.rules('public OnPlayerUpdate(p){ if(IsPlayerInRangeOfPoint(p, 5.0, 0.0, 0.0, 0.0)) return 1; return 1; }'))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest discover -s plugins/pawn-forge/tests -t plugins/pawn-forge/tests -p test_lint.py -v`
Expected: FAIL (`PF701`–`PF802` not in `RULES` / findings empty).

- [ ] **Step 3: Implement `PF701`–`PF704` and `PF801`–`PF802` in `plugins/pawn-forge/server/pawnforge/lint.py`**

Add rule definitions in `RULES`:
- `PF701` (warning, `security`): Immediate `Kick`/`Ban`/`BanEx` after `SendClientMessage`/`ShowPlayerDialog` in the same execution path (use a short `SetTimerEx`/`defer` delay so the message reaches the client before disconnect).
- `PF702` (error, `security`): Unguarded `strcmp` on `inputtext` (in Pawn `strcmp("pw", "")` returns `0`; guard with `isnull(inputtext)`, `!inputtext[0]`, or `strlen(inputtext)` before comparing).
- `PF703` (warning, `security`): Combat callback (`OnPlayerWeaponShot`, `OnPlayerGiveDamage`, `OnPlayerTakeDamage`) indexes an array with a client-supplied parameter without a bounds check (`< 0`, `>= sizeof`, `INVALID_PLAYER_ID`, `IsPlayerConnected`).
- `PF704` (error, `security`): `SendRconCommand` called with a buffer built using `format(..., "%s", ...)`.
- `PF801` (warning, `ecosystem`): `BS_New`/`BS_NewCopy` BitStream not freed with `BS_Delete` in the function.
- `PF802` (info, `performance`): `IsPlayerInRangeOfPoint` inside `OnPlayerUpdate`.

Implement conservative `check_immediate_kick`, `check_empty_strcmp`, `check_combat_bounds`, `check_rcon_injection`, `check_bitstream_leaks`, and `check_range_in_onplayerupdate` on `Linter`.

- [ ] **Step 4: Run `test_lint.py` (including `test_all_rules_covered` and `test_clean_modern_code_is_quiet`)**

Run: `python -m unittest discover -s plugins/pawn-forge/tests -t plugins/pawn-forge/tests -v`
Expected: PASS (all rules covered, zero false positives).

- [ ] **Step 5: Commit**

```bash
git add plugins/pawn-forge/server/pawnforge/lint.py plugins/pawn-forge/tests/fixtures/legacy_bad.pwn plugins/pawn-forge/tests/test_lint.py
git commit -m "feat: add SA-MP anti-cheat, security, and ecosystem lint rules (PF701-PF802)"
```

---

## Task 5: Portable Bootstrapper & Canonical Core/Workflow Skills (`skills/pawn-*`)

**Files:**
- Create: `plugins/pawn-forge/tools/pawnforge_exec.py` (canonical source copied into `skills/<tool-skill>/scripts/pawnforge_exec.py`)
- Create: `skills/pawn-standards/SKILL.md` and `skills/pawn-standards/references/{commands-and-input,legacy-to-modern,mysql-r41,streamer,strings-and-buffers,ysi}.md`
- Create: `skills/pawn-build/SKILL.md` (+ `scripts/pawnforge_exec.py`)
- Create: `skills/pawn-audit/SKILL.md` (+ `scripts/pawnforge_exec.py`)
- Create: `skills/pawn-debug-crash/SKILL.md` (+ `scripts/pawnforge_exec.py`)
- Create: `skills/pawn-migrate-openmp/SKILL.md` (+ `scripts/pawnforge_exec.py`)
- Create: `skills/pawn-modernize-storage/SKILL.md` (+ `scripts/pawnforge_exec.py`)
- Create: `skills/pawn-test/SKILL.md` (+ `scripts/pawnforge_exec.py`)
- Create: `skills/pawn-textdraw/SKILL.md` (+ `scripts/pawnforge_exec.py`)
- Create: `skills/pawn-standards/scripts/pawnforge_exec.py`

**Interfaces:**
- Consumes: `pawnforge` CLI (Task 3) and MCP tools (`tools.py`).
- Produces: Canonical Agensi-compliant `SKILL.md` files under `skills/` + portable `scripts/pawnforge_exec.py` CLI locator.

- [ ] **Step 1: Write `plugins/pawn-forge/tools/pawnforge_exec.py`**

Implement a stdlib-only (<80 lines) Python wrapper script accepting any `pawnforge` CLI arguments:
1. Search `shutil.which("pawnforge")`.
2. Search `importlib.util.find_spec("pawnforge")`.
3. Search workspace / standard plugin paths (`.agents/plugins/pawn-forge/server`, `./plugins/pawn-forge/server`, `~/.gemini/config/plugins/pawn-forge/server`, `~/.claude/plugins/` recursively for `pawnforge/cli.py`).
4. Execute found target via `subprocess.run`, forwarding stdout/stderr and exit code; if not found, print JSON `{"ok": false, "error": "pawnforge CLI not installed", "install": "pip install git+https://github.com/POORSAKEN2/pawn-forge.git"}` and exit `1`.

- [ ] **Step 2: Author `skills/pawn-standards/SKILL.md` and port its 6 `references/*.md` files**

Ensure frontmatter strictly complies with `agentskills.io`:
```yaml
---
name: pawn-standards
description: Modern, safe Pawn for SA-MP 0.3.7 and open.mp game servers. Use when writing, reviewing, refactoring, or explaining Pawn (.pwn/.inc) gamemodes, filterscripts, or includes.
license: MIT
compatibility: Optional Python 3.8+ for pawnforge CLI / MCP verification and pawncc 3.10.x compiler.
metadata:
  author: POORSAKEN2
  version: "0.2.0"
---
```
Update Section 1 & 2 to document the Tool Resolution Order (MCP -> `pawnforge` CLI / `scripts/pawnforge_exec.py` -> direct `pawncc`) and first-class SA-MP 0.3.7 support (`platform="sa-mp"` vs `"open.mp"`), preserving all buffer, DB, command, loop, and structure rules. Copy/adapt the 6 existing reference markdown files under `skills/pawn-standards/references/` (replacing MCP-only wording with portable `api_lookup` / `pawnforge api` phrasing).

- [ ] **Step 3: Author the 7 workflow skills (`pawn-build`, `pawn-audit`, `pawn-debug-crash`, `pawn-migrate-openmp`, `pawn-modernize-storage`, `pawn-test`, `pawn-textdraw`)**

Each skill has:
- Valid `agentskills.io` frontmatter (`name:` matching folder name, `description:` <= 1024 chars with trigger conditions, `license: MIT`, `compatibility`, `metadata`, NO non-portable `mcp__plugin_*` names in `allowed-tools` or prose).
- Uniform **Tool Resolution** block at the top (MCP tools if present, else `python scripts/pawnforge_exec.py <cmd> --json` / `pawnforge <cmd> --json`).
- Updated `pawn-audit` checklist explicitly cross-referencing `PF701`–`PF802`, `pawn-roleplay`, and `pawn-anticheat`.
- Copy `plugins/pawn-forge/tools/pawnforge_exec.py` into each skill's `scripts/pawnforge_exec.py`.

- [ ] **Step 4: Write and run isolated standalone `pawnforge_exec.py` tests in `plugins/pawn-forge/tests/test_cli.py`**

Add `test_pawnforge_exec_standalone_and_missing_fallback` to `test_cli.py`: copy `pawnforge_exec.py` to a `TemporaryDirectory` outside the repo, run it with `PYTHONPATH=plugins/pawn-forge/server` (`lookup vehicle infernus --json`) asserting `returncode == 0` and `"id": 411`, and run it with an empty `PATH` and clean `PYTHONPATH` / mocked missing paths asserting `returncode == 1` and valid JSON containing `"ok": false` and `"install"`.
Run: `python -m unittest discover -s plugins/pawn-forge/tests -t plugins/pawn-forge/tests -p test_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/pawn-forge/tools/pawnforge_exec.py skills/
git commit -m "feat: create Agensi-compatible canonical skills and portable CLI bootstrapper"
```

---

## Task 6: Roleplay Systems Skill (`skills/pawn-roleplay/`) & Compilable Snippets

**Files:**
- Create: `skills/pawn-roleplay/SKILL.md`
- Create: `skills/pawn-roleplay/references/accounts-and-characters.md`
- Create: `skills/pawn-roleplay/references/inventory-and-items.md`
- Create: `skills/pawn-roleplay/references/vehicles-and-properties.md`
- Create: `skills/pawn-roleplay/references/factions-economy-chat.md`
- Create: `plugins/pawn-forge/tests/fixtures/doc_snippets/rp_inventory.pwn`
- Create: `plugins/pawn-forge/tests/fixtures/doc_snippets/rp_vehicle_house.pwn`
- Modify: `plugins/pawn-forge/tests/test_integration.py`

**Interfaces:**
- Consumes: `pawn-standards` conventions, `pawnforge` CLI / `api_lookup` / `lookup`.
- Produces: Complete `pawn-roleplay` skill + 4 focused references + 2 compilable doc snippet fixtures.

- [ ] **Step 1: Author `skills/pawn-roleplay/SKILL.md` (<120 lines)**

Frontmatter `name: pawn-roleplay`, concise non-negotiable RP engineering rules (single source of truth in server memory, race-checked async MySQL R41 / SQLite persistence, atomic inventory/money transfers, virtual-world/interior isolation, 144-char chat line wrapping, zero-trust dialog/input validation) and reference router to the 4 guides.

- [ ] **Step 2: Author the 4 reference guides under `skills/pawn-roleplay/references/`**

- `accounts-and-characters.md`: Multi-character SQL schema, `gRace[playerid]` async race guards, dirty-flag staggered auto-save vs immediate critical writes, `samp-bcrypt` auth flow, safe spawn state (`Streamer_UpdateEx`).
- `inventory-and-items.md`: Normalized `character_items` relational table, `enum E_ITEM_TYPE` static metadata table, slot/weight/stack validation, duplication-proof `Inventory_Transfer` with trade-lock/save-lock flags.
- `vehicles-and-properties.md`: Persistent SQL `db_id` vs runtime `vehicleid`, `GetVehicleParamsEx`/`SetVehicleParamsEx` engine/lights/doors, trunk inventories, `OnVehicleDeath` restoration; house/business pickups, Streamer dynamic areas, `VW_HOUSE_BASE + houseid` isolation, interior lookups via `lookup kind=interior`.
- `factions-economy-chat.md`: Faction types/ranks/duty loadout save-restore, overflow-safe `Money_Transfer(from, to, amount)` (`MAX_SAFE_MONEY = 1_000_000_000`, `cellmax - cash` guard), proximity chat (`GetPlayerPos`, `VectorSize`, matching VW + interior, clean 2-line 144-char split for `/me`, `/do`, `/s`, `/w`, `/b`).

- [ ] **Step 3: Create `rp_inventory.pwn` and `rp_vehicle_house.pwn` snippets and register in `test_integration.py`**

Create standalone compilable Pawn modules matching the reference patterns under `plugins/pawn-forge/tests/fixtures/doc_snippets/`, add them to `SNIPPETS` in `test_integration.py`, and run `pawnforge lint` on both snippets ensuring 0 findings at `warning`/`error` severity.

- [ ] **Step 4: Run unit & lint verification on the new snippets**

Run: `python -m unittest discover -s plugins/pawn-forge/tests -t plugins/pawn-forge/tests -v`
Run: `PYTHONPATH=plugins/pawn-forge/server python -m pawnforge lint plugins/pawn-forge/tests/fixtures/doc_snippets/rp_inventory.pwn --min-severity warning --json`
Run: `PYTHONPATH=plugins/pawn-forge/server python -m pawnforge lint plugins/pawn-forge/tests/fixtures/doc_snippets/rp_vehicle_house.pwn --min-severity warning --json`
Expected: PASS (`summary.error == 0`, `summary.warning == 0`).

- [ ] **Step 5: Commit**

```bash
git add skills/pawn-roleplay/ plugins/pawn-forge/tests/fixtures/doc_snippets/rp_inventory.pwn plugins/pawn-forge/tests/fixtures/doc_snippets/rp_vehicle_house.pwn plugins/pawn-forge/tests/test_integration.py
git commit -m "feat: add pawn-roleplay skill with verified reference patterns and snippets"
```

---

## Task 7: Anti-Cheat & Security Skill (`skills/pawn-anticheat/`) & Compilable Snippets

**Files:**
- Create: `skills/pawn-anticheat/SKILL.md`
- Create: `skills/pawn-anticheat/references/server-authoritative-state.md`
- Create: `skills/pawn-anticheat/references/movement-and-combat.md`
- Create: `skills/pawn-anticheat/references/raknet-and-nexac.md`
- Create: `plugins/pawn-forge/tests/fixtures/doc_snippets/ac_weapons_cash.pwn`
- Create: `plugins/pawn-forge/tests/fixtures/doc_snippets/ac_dialogs_kick.pwn`
- Modify: `plugins/pawn-forge/tests/test_integration.py`

**Interfaces:**
- Consumes: `pawn-standards`, `pawn-ecosystem` (RakNet), `pawnforge` lint rules `PF701`–`PF704`.
- Produces: Complete `pawn-anticheat` skill + 3 focused references + 2 compilable doc snippet fixtures.

- [ ] **Step 1: Author `skills/pawn-anticheat/SKILL.md` (<120 lines)**

Frontmatter `name: pawn-anticheat`, threat model rules (never trust client cash/weapons/health/dialogid/position, lag-tolerant grace windows, delayed `Kick` via `SetTimerEx`/`defer`, bounds-check combat callbacks), and reference router.

- [ ] **Step 2: Author the 3 reference guides under `skills/pawn-anticheat/references/`**

- `server-authoritative-state.md`: Shadow `sPlayerCash`, `sPlayerWeapons[13]`, `sPlayerAmmo[13]`, `sWeaponGraceUntil` timestamps, vehicle-entry weapon exceptions (Police Car shotgun, Caddy golf club, aircraft parachute), `EnableStuntBonusForAll(false)`, server-side health/armour model.
- `movement-and-combat.md`: `GetTickCount()` delta speed/teleport checks with `AC_SetPlayerPos` grace windows, passenger/surfing/falling exclusions, `OnPlayerWeaponShot` NaN (`val != val`), bullet distance & rapid-fire timing, `OnPlayerGiveDamage` cross-checks, server-tracked `sActiveDialog[playerid]`, `isnull(inputtext)` guard against empty-`strcmp` bypass, delayed `Kick` pattern.
- `raknet-and-nexac.md`: `Pawn.RakNet` incoming packet/RPC checks (IDs `207` player sync, `200` vehicle sync, `211` passenger sync, `206` bullet sync, RPC `62` DialogResponse, `115` GiveTakeDamage, `106` DamageVehicle — dropping NaN/Inf floats, invalid seats, crashers), plus `nex-ac` include placement and custom `OnCheatDetected` / whitelist integration.

- [ ] **Step 3: Create `ac_weapons_cash.pwn` and `ac_dialogs_kick.pwn` snippets and register in `test_integration.py`**

Ensure both snippets compile clean conceptually, adhere strictly to `PF701`–`PF704` (zero lint errors/warnings), and register them in `SNIPPETS` in `test_integration.py`.

- [ ] **Step 4: Run lint & unit verification**

Run: `python -m unittest discover -s plugins/pawn-forge/tests -t plugins/pawn-forge/tests -v`
Run: `PYTHONPATH=plugins/pawn-forge/server python -m pawnforge lint plugins/pawn-forge/tests/fixtures/doc_snippets/ac_weapons_cash.pwn --min-severity warning --json`
Run: `PYTHONPATH=plugins/pawn-forge/server python -m pawnforge lint plugins/pawn-forge/tests/fixtures/doc_snippets/ac_dialogs_kick.pwn --min-severity warning --json`
Expected: PASS (`summary.error == 0`, `summary.warning == 0`).

- [ ] **Step 5: Commit**

```bash
git add skills/pawn-anticheat/ plugins/pawn-forge/tests/fixtures/doc_snippets/ac_weapons_cash.pwn plugins/pawn-forge/tests/fixtures/doc_snippets/ac_dialogs_kick.pwn plugins/pawn-forge/tests/test_integration.py
git commit -m "feat: add pawn-anticheat skill with authoritative state and RakNet references"
```

---

## Task 8: Specific Include Ecosystems Skill (`skills/pawn-ecosystem/`) & Snippets

**Files:**
- Create: `skills/pawn-ecosystem/SKILL.md`
- Create: `skills/pawn-ecosystem/references/pawn-raknet.md`
- Create: `skills/pawn-ecosystem/references/ysi5-deep-dive.md`
- Create: `skills/pawn-ecosystem/references/streamer-and-world.md`
- Create: `skills/pawn-ecosystem/references/colandreas-and-physics.md`
- Create: `skills/pawn-ecosystem/references/auth-and-commands.md`
- Create: `plugins/pawn-forge/tests/fixtures/doc_snippets/eco_streamer_areas.pwn`
- Modify: `plugins/pawn-forge/tests/test_integration.py`

**Interfaces:**
- Consumes: `api_lookup` / `pawnforge api` signatures from Task 2 (`pawn.raknet`, `samp-bcrypt`, `colandreas`, `streamer`, `mysql-r41`, `sscanf`, `pawn.cmd`).
- Produces: Complete `pawn-ecosystem` skill + 5 focused references + `eco_streamer_areas.pwn` fixture.

- [ ] **Step 1: Author `skills/pawn-ecosystem/SKILL.md` (<120 lines)**

Frontmatter `name: pawn-ecosystem`, library selection matrix, strict include ordering (`<a_samp>`/`<open.mp>` -> C++ plugin headers -> YSI 5 -> local modules), SA-MP 0.3.7 plugin vs open.mp component deployment differences, and reference router.

- [ ] **Step 2: Author the 5 reference guides under `skills/pawn-ecosystem/references/`**

- `pawn-raknet.md`: BitStream allocation (`BS_New`/`BS_Delete`), `BS_ResetReadPointer`, `BS_ReadValue`/`BS_WriteValue`, `OnIncomingPacket`/`OnIncomingRPC`/`OnOutgoingRPC`, `IRPC:`/`IPacket:` handlers, sync data structures, SA-MP 1.5.x vs open.mp `1.6.x-omp` component notes.
- `ysi5-deep-dive.md`: `y_inline` + `y_inline_mysql` + `y_inline_timers`, `y_dialog` (`Dialog_ShowCallback`), `y_va`, `y_bits`/`BitArray`, `y_groups`, `y_master`, compile macros (`YSI_NO_HEAP_MALLOC`, `YSI_NO_OPTIMISATION_MESSAGE`).
- `streamer-and-world.md`: `Streamer_SetMaxItems`, `Streamer_SetVisibleItems`, `Streamer_SetTickRate`, `Streamer_SetCellDistance`, dynamic polygons/circles/spheres/cuboids, `AttachDynamicObjectToVehicle`, `AttachDynamicAreaToPlayer`, `E_STREAMER_PLAYER_ID`, `Streamer_UpdateEx`.
- `colandreas-and-physics.md`: `ColAndreas` (`CA_Init`, `CA_RayCastLine`, `CA_RayCastLineEx`, `CA_FindZ_For2DCoord`, syncing `CA_CreateObject` with custom Streamer maps) + `MapAndreas` lightweight Z-height fallback.
- `auth-and-commands.md`: `Sreyas-Sreelal/samp-bcrypt` (`#include <samp_bcrypt>`, `bcrypt_hash`, `bcrypt_verify`, `bcrypt_is_equal`, cost 10-12, race checks) vs `lassir/bcrypt-samp` (`#include <bcrypt>`, `bcrypt_check`) note, `Pawn.CMD` vs `YCMD` vs `I-ZCMD`, advanced `sscanf2` specifiers (`k<weapon>`, `k<vehicle>`, `e<...>`, `p<...>`), `easyDialog` & `mSelection`.
- Verify every native signature cited in the references against `api_lookup` / `pawnforge api`!

- [ ] **Step 3: Create `eco_streamer_areas.pwn` snippet, register in `test_integration.py`, and lint**

Run: `PYTHONPATH=plugins/pawn-forge/server python -m pawnforge lint plugins/pawn-forge/tests/fixtures/doc_snippets/eco_streamer_areas.pwn --min-severity warning --json`
Expected: PASS (`summary.error == 0`, `summary.warning == 0`).

- [ ] **Step 4: Commit**

```bash
git add skills/pawn-ecosystem/ plugins/pawn-forge/tests/fixtures/doc_snippets/eco_streamer_areas.pwn plugins/pawn-forge/tests/test_integration.py
git commit -m "feat: add pawn-ecosystem skill covering Pawn.RakNet, YSI 5, Streamer, ColAndreas, and bcrypt"
```

---

## Task 9: Sync Engine, Skill Validation Tests, Plugin Updates & Documentation

**Files:**
- Create: `plugins/pawn-forge/tools/sync_skills.py`
- Modify/Create: `plugins/pawn-forge/skills/*` (generated/synced via `sync_skills.py`)
- Create: `plugins/pawn-forge/tests/test_skills.py`
- Modify: `plugins/pawn-forge/agents/pawn-auditor.md`
- Modify: `plugins/pawn-forge/agents/pawn-build-fixer.md`
- Modify: `plugins/pawn-forge/scripts/session_start.py`
- Modify: `README.md`
- Modify: `plugins/pawn-forge/README.md`

**Interfaces:**
- Consumes: `skills/` (Tasks 5-8)
- Produces: `plugins/pawn-forge/tools/sync_skills.py` (`sync(check: bool = False) -> bool`), synchronized `plugins/pawn-forge/skills/`, `test_skills.py`, updated agent/hook/doc files.

- [ ] **Step 1: Write the failing test `plugins/pawn-forge/tests/test_skills.py`**

```python
import re
import subprocess
import sys
import unittest
from pathlib import Path

from helpers import PLUGIN

REPO_ROOT = PLUGIN.parent.parent
SKILLS_ROOT = REPO_ROOT / "skills"


class SkillsTest(unittest.TestCase):
    def test_agensi_skill_frontmatter_and_links(self):
        dirs = sorted(p for p in SKILLS_ROOT.iterdir() if p.is_dir())
        self.assertGreaterEqual(len(dirs), 11)
        for d in dirs:
            skill_md = d / "SKILL.md"
            self.assertTrue(skill_md.is_file(), f"missing SKILL.md in {d}")
            text = skill_md.read_text(encoding="utf-8")
            m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
            self.assertIsNotNone(m, f"missing YAML frontmatter in {skill_md}")
            fm = m.group(1)
            name_m = re.search(r"^name:\s*(.+)$", fm, re.M)
            desc_m = re.search(r"^description:\s*(.+)$", fm, re.M)
            self.assertIsNotNone(name_m, f"missing name in {skill_md}")
            self.assertEqual(name_m.group(1).strip(), d.name)
            self.assertRegex(d.name, r"^[a-z0-9-]{1,64}$")
            self.assertIsNotNone(desc_m, f"missing description in {skill_md}")
            self.assertLessEqual(len(desc_m.group(1).strip()), 1024)
            self.assertNotIn("mcp__plugin_pawn-forge_pawn__", text)
            for link in re.findall(r"\[[^\]]+\]\(([^)#:]+\.(?:md|py))\)", text):
                self.assertTrue((d / link).exists(), f"broken link {link} in {skill_md}")

    def test_plugin_skills_in_sync(self):
        r = subprocess.run([sys.executable, str(PLUGIN / "tools" / "sync_skills.py"), "--check"],
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest discover -s plugins/pawn-forge/tests -t plugins/pawn-forge/tests -p test_skills.py -v`
Expected: FAIL (`sync_skills.py` not found / `plugins/pawn-forge/skills/` out of sync).

- [ ] **Step 3: Implement `plugins/pawn-forge/tools/sync_skills.py` and run sync**

- Define the exact rename map:
  - `pawn-standards` -> `pawn-standards`
  - `pawn-build` -> `build`
  - `pawn-audit` -> `audit`
  - `pawn-debug-crash` -> `debug-crash`
  - `pawn-migrate-openmp` -> `migrate-openmp`
  - `pawn-modernize-storage` -> `modernize-storage`
  - `pawn-test` -> `test`
  - `pawn-textdraw` -> `textdraw`
  - `pawn-roleplay` -> `roleplay`
  - `pawn-anticheat` -> `anticheat`
  - `pawn-ecosystem` -> `ecosystem`
- Mirror `references/` and `scripts/` cleanly, rewrite frontmatter `name:` to match target directory name, rewrite cross-skill references in plugin `SKILL.md` (`pawn-audit` -> `audit` etc., while leaving `pawn-standards` as `pawn-standards`), delete orphaned files in destination skill dirs, and copy `plugins/pawn-forge/tools/pawnforge_exec.py` into both root and plugin tool-using skills so source never drifts.
- Support `--check` (exits `1` if any file differs or is missing/extra).
- Run `python plugins/pawn-forge/tools/sync_skills.py` to generate synced `plugins/pawn-forge/skills/`.

- [ ] **Step 4: Update `agents/`, `session_start.py`, `README.md`, and `plugins/pawn-forge/README.md`**

- Update `plugins/pawn-forge/agents/pawn-auditor.md`: add `PF701`–`PF802` checks (delayed kick, unguarded `strcmp`, combat bounds, RakNet BitStream leaks).
- Update `plugins/pawn-forge/agents/pawn-build-fixer.md`: mention SA-MP 0.3.7 (`platform="sa-mp"`) and `Pawn.RakNet`/`ColAndreas`/`samp-bcrypt` lookup support.
- Update `plugins/pawn-forge/scripts/session_start.py`: list new workflows (`/pawn-forge:roleplay`, `/pawn-forge:anticheat`, `/pawn-forge:ecosystem`).
- Update `README.md` and `plugins/pawn-forge/README.md`:
  - Add **Agensi & Multi-Agent Quick Start** (`npx skills add POORSAKEN2/pawn-forge` for Claude Code, Cursor, GitHub Copilot, Windsurf, Codex, Antigravity, and 20+ agents + standalone CLI `pip install git+...` / `pawnforge` usage).
  - Update Antigravity plugin install instructions so `.agents/plugins/pawn-forge` points cleanly without duplicate skill exposure.
  - Document the 11 skills (`pawn-roleplay`, `pawn-anticheat`, `pawn-ecosystem`, etc.) and new lint rules (`PF701`–`PF802`).

- [ ] **Step 5: Run full verification suite & `sync_skills.py --check`**

Run: `python plugins/pawn-forge/tools/sync_skills.py --check`
Run: `python -m unittest discover -s plugins/pawn-forge/tests -t plugins/pawn-forge/tests -v`
Expected: PASS (all unit tests pass with 0 failures; `sync_skills.py --check` exits `0`).

- [ ] **Step 6: Commit**

```bash
git add plugins/pawn-forge/tools/sync_skills.py plugins/pawn-forge/skills/ plugins/pawn-forge/tests/test_skills.py plugins/pawn-forge/agents/ plugins/pawn-forge/scripts/session_start.py README.md plugins/pawn-forge/README.md
git commit -m "feat: add Agensi skill sync, validation tests, agent updates, and multi-agent docs"
```

---

## Self-Review Checklist (Executed)

1. **Spec Coverage:** Every spec item maps to a task:
   - Root `skills/` (`pawn-*`) & `plugins/pawn-forge/skills/` sync -> Tasks 5, 9
   - Standalone CLI + `pyproject.toml` + `pawnforge_exec.py` -> Tasks 3, 5
   - SA-MP `api_lookup` filtering + `project_info` new libraries + `build_data.py` & `server/data/*.json` regeneration -> Tasks 1, 2
   - `PF701`–`PF802` lint rules -> Task 4
   - `pawn-roleplay`, `pawn-anticheat`, `pawn-ecosystem` skills + compilable snippets -> Tasks 6, 7, 8
   - Tests (`test_cli.py`, `test_skills.py`, `test_lint.py`, `test_tools.py`, `test_integration.py`) + README/agent/hook updates -> Tasks 1-9
2. **Type & Interface Consistency:** `collect_project_includes`, `api_lookup(..., platform="auto")`, `pawnforge.cli.main`, `pawnforge_exec.py`, `sync_skills.py --check`, and `PF701`–`PF802` are consistently named across every task.
3. **Review Focus Coverage:** All 5 edge cases in Review Focus have explicit test steps in Tasks 1, 2, 3, 4, and 5/9.
