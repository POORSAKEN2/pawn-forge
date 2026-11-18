import json
import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from helpers import FIXTURES, PLUGIN

from pawnforge import api, data, lookup, project, tools
from pawnforge.crashlog import analyze_log
from pawnforge.migrate import migrate_openmp
from pawnforge.textdraw import convert_textdraws


class DataTest(unittest.TestCase):
    def test_counts(self):
        self.assertEqual(len(data.load("vehicles")), 212)
        self.assertEqual(min(data.vehicle_ids()), 400)
        self.assertEqual(max(data.vehicle_ids()), 611)
        self.assertEqual(len(data.skin_ids()), 311)
        self.assertNotIn(74, data.skin_ids())
        self.assertNotIn(19, data.givable_weapon_ids())
        self.assertIn(46, data.givable_weapon_ids())
        self.assertGreater(len(data.load("animations")), 1500)
        self.assertGreater(len(data.load("natives")), 1000)


class LookupTest(unittest.TestCase):
    def test_vehicle(self):
        r = lookup.lookup("vehicle", "infernus")
        self.assertEqual(r["results"][0]["id"], 411)
        self.assertEqual(len(r["results"]), 1)
        self.assertFalse(lookup.lookup("vehicle", 399)["valid"])

    def test_skin_74(self):
        r = lookup.lookup("skin", 74)
        self.assertFalse(r["valid"])

    def test_weapon_constant(self):
        r = lookup.lookup("weapon", "WEAPON_DEAGLE")
        self.assertEqual(r["results"][0]["id"], 24)

    def test_animation(self):
        r = lookup.lookup("animation", "WALK_civi", library="ped")
        self.assertTrue(r["valid"])
        self.assertIn("ApplyAnimation", r["usage"])
        self.assertFalse(lookup.lookup("animation", "x", library="PEDS")["valid"])

    def test_interior(self):
        r = lookup.lookup("interior", "24/7")
        self.assertTrue(r["results"])
        self.assertIn("interior", r["results"][0])


class ApiTest(unittest.TestCase):
    def test_exact(self):
        r = api.api_lookup(name="mysql_tquery")
        self.assertTrue(r["found"])
        self.assertIn("callback", r["results"][0]["signature"])

    def test_deprecated(self):
        r = api.api_lookup(name="GetPlayerPoolSize")
        self.assertIn("openmp_deprecation", r)

    def test_suggestions(self):
        r = api.api_lookup(name="CreateDynamicObj")
        self.assertFalse(r["found"])
        self.assertIn("CreateDynamicObject", r["did_you_mean"])

    def test_project_includes(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "include").mkdir()
            Path(d, "include", "mylib.inc").write_text("native MyLib_Do(playerid, const what[]);\n")
            Path(d, "gamemodes").mkdir()
            r = api.api_lookup(name="MyLib_Do", project_dir=d)
            self.assertTrue(r["found"])
            self.assertTrue(r["results"][0]["library"].startswith("project:"))


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

                explicit_lib = api.api_lookup(name="GetPlayerPoolSize", library="samp-stdlib")
                self.assertEqual([r["library"] for r in explicit_lib["results"]], ["samp-stdlib"])
                self.assertNotIn("openmp_deprecation", explicit_lib)

                via_tool = tools.call_tool("api_lookup", {"name": "GetPlayerPoolSize", "platform": "samp"})
                self.assertEqual([r["library"] for r in via_tool["results"]], ["samp-stdlib"])
                self.assertNotIn("openmp_deprecation", via_tool)

    def test_collect_includes_exclusions_and_remaining_libraries(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "pawno" / "include").mkdir(parents=True)
            (root / "pawno" / "include" / "a_samp.inc").write_text("#include <a_samp>\n")
            (root / "include" / "dependencies").mkdir(parents=True)
            (root / "include" / "dependencies" / "ignored.inc").write_text("#include <open.mp>\n")
            (root / "src").mkdir()
            (root / "src" / "main.inc").write_text(
                "#include <a_samp>\n#include <mapandreas>\n#include <mSelection>\n"
                "#include <bcrypt>\n#include <nex_ac>\n"
            )
            info = project.project_info(d)
            self.assertEqual(info["platform"], "sa-mp")
            for lib in ("mapandreas", "mselection", "samp-bcrypt", "nex-ac"):
                self.assertIn(lib, info["libraries_detected"])
            self.assertNotIn("open.mp", [i.lower() for i in info["includes_in_main"]])

    def test_bundled_samp_ecosystem_apis_present(self):
        self.assertTrue(api.api_lookup(name="BS_New")["found"])
        self.assertTrue(api.api_lookup(name="bcrypt_hash")["found"])
        self.assertTrue(api.api_lookup(name="CA_RayCastLine")["found"])
        samp = api.api_lookup(name="SendClientMessage", platform="sa-mp")
        self.assertTrue(samp["found"])
        self.assertEqual(samp["results"][0]["library"], "samp-stdlib")
        self.assertIn("samp-stdlib", data.load("sources"))


class CrashlogTest(unittest.TestCase):
    def test_fixture(self):
        r = analyze_log(path=str(FIXTURES / "server_log.txt"), source_root=str(FIXTURES / "src"))
        groups = {(g["type"], g.get("code")): g for g in r["incidents"]}
        oob = [g for g in r["incidents"] if g.get("code") == 4]
        self.assertEqual(len(oob), 2)
        top = max(oob, key=lambda g: g["count"])
        self.assertEqual(top["count"], 2)
        self.assertEqual((top["index"], top["array_size"]), (11, 10))
        self.assertTrue(top["amx_backtrace"][0]["context"])
        invalid = [g for g in oob if g.get("index") == 65535][0]
        self.assertEqual(invalid["array_size"], 1000)
        self.assertIn("INVALID_PLAYER_ID", invalid["hint"])
        self.assertIn(("long_callback", None), groups)
        self.assertEqual(groups[("crash", None)]["suspect_module"], "plugins/mysql.so")
        self.assertEqual(r["missing_natives"], ["CreateDynamic3DTextLabel", "CreateDynamicObject"])
        self.assertTrue(r["plugin_failures"])

    def test_openmp_prefixes(self):
        text = ('[2026-10-19T11:00:00+0800] [Info] [debug] Run time error 11: "Divide by zero"\n'
                '[2026-10-19T11:00:00+0800] [Info] [debug] AMX backtrace:\n'
                '[2026-10-19T11:00:00+0800] [Info] [debug] #0 00000010 in Ratio (a=1, b=0) at gm.pwn:5\n')
        r = analyze_log(text=text)
        self.assertEqual(r["incidents"][0]["code"], 11)
        self.assertEqual(r["incidents"][0]["amx_backtrace"][0]["line"], 5)


class MigrateTest(unittest.TestCase):
    def test_fixture(self):
        r = migrate_openmp(file=str(FIXTURES / "legacy_samp.pwn"), write="return")
        code = r["migrated_code"]
        for expected in ("#include <open.mp>", "DB_Open(", "DB_FreeResultSet(DB_ExecuteQuery(", "TEXT_DRAW_FONT_3",
                         "TEXT_DRAW_ALIGN_CENTER", "TextDrawColour(", "TogglePlayerControllable(playerid, true)",
                         "WEAPON_DEAGLE", "OnPlayerDeath(playerid, killerid, WEAPON:reason)", "1958.0"):
            self.assertIn(expected, code)
        self.assertIn("GetPlayerPoolSize", code)  # manual item: reported, not rewritten
        self.assertTrue(any(i["kind"] == "deprecated" and not i["safe"] for i in r["items"]))

    def test_write_copy_and_backup(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "gm.pwn")
            p.write_text((FIXTURES / "legacy_samp.pwn").read_text())
            r = migrate_openmp(file=str(p), write="copy")
            self.assertTrue(Path(r["written"]).exists())
            self.assertIn("<a_samp>", p.read_text())
            r = migrate_openmp(file=str(p), write="in_place")
            self.assertIn("<open.mp>", p.read_text())
            self.assertIn("<a_samp>", Path(r["backup"]).read_text())


class TextDrawTest(unittest.TestCase):
    def test_fixture(self):
        r = convert_textdraws((FIXTURES / "td_export.pwn").read_text(), prefix="Speedo")
        self.assertTrue(r["ok"])
        self.assertEqual((r["globals"], r["player"]), (2, 2))
        self.assertEqual(len(r["warnings"]), 2)
        self.assertIn("TextDrawColour(", r["code"])
        self.assertIn("TEXT_DRAW_ALIGN_CENTER", r["code"])
        self.assertIn("static bool:Speedo_pCreated[MAX_PLAYERS];", r["code"])

    def test_bad_prefix(self):
        self.assertFalse(convert_textdraws("x = TextDrawCreate(1.0, 2.0, \"a\");", prefix="1bad")["ok"])

    def test_no_textdraws(self):
        self.assertFalse(convert_textdraws("main(){}")["ok"])


class McpTest(unittest.TestCase):
    def test_protocol(self):
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "lookup", "arguments": {"kind": "skin", "query": 0}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "lint", "arguments": {"code": "f(){ new a[2]; format(a, 9, \"x\"); }"}}},
            {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "missing", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 6, "method": "bogus/method"},
        ]
        p = subprocess.run([sys.executable, str(PLUGIN / "server" / "pawn_mcp.py")],
                           input="\n".join(json.dumps(m) for m in msgs) + "\n",
                           capture_output=True, text=True, timeout=60)
        out = {m["id"]: m for m in map(json.loads, p.stdout.splitlines())}
        self.assertEqual(out[1]["result"]["protocolVersion"], "2025-06-18")
        names = {t["name"] for t in out[2]["result"]["tools"]}
        self.assertEqual(len(names), 11)
        for t in out[2]["result"]["tools"]:
            self.assertEqual(t["inputSchema"]["type"], "object")
        self.assertFalse(out[3]["result"]["isError"])
        self.assertIn("PF102", out[4]["result"]["content"][0]["text"])
        self.assertTrue(out[5]["result"]["isError"])
        self.assertEqual(out[6]["error"]["code"], -32601)
        self.assertEqual(p.stdout.count("\n"), 6)  # notification gets no reply


class HookTest(unittest.TestCase):
    def run_hook(self, script, payload, env=None):
        e = dict(os.environ, **(env or {}))
        return subprocess.run([sys.executable, str(PLUGIN / "scripts" / script)], input=json.dumps(payload),
                              capture_output=True, text=True, timeout=60, env=e)

    def test_lint_hook_reports_only_changed_lines(self):
        f = str(FIXTURES / "legacy_bad.pwn")
        new = '\tformat(msg, sizeof msg, "Welcome %s (%d)", name);'
        r = self.run_hook("lint_hook.py", {"tool_name": "Edit", "tool_input": {"file_path": f, "new_string": new}})
        ctx = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("PF104", ctx)
        self.assertIn("1 issue", ctx)

    def test_lint_hook_silent_cases(self):
        r = self.run_hook("lint_hook.py", {"tool_name": "Edit", "tool_input": {"file_path": "/x/readme.md", "new_string": "a"}})
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        r = self.run_hook("lint_hook.py", {"tool_name": "Write", "tool_input": {"file_path": str(FIXTURES / "legacy_bad.pwn")}},
                          {"CLAUDE_PLUGIN_OPTION_LINT_ON_EDIT": "false"})
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        r = subprocess.run([sys.executable, str(PLUGIN / "scripts" / "lint_hook.py")], input="not json",
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0)

    def test_session_start(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_hook("session_start.py", {"cwd": d}, {"CLAUDE_PROJECT_DIR": d})
            self.assertEqual(r.stdout, "")
            Path(d, "gamemodes").mkdir()
            Path(d, "gamemodes", "gm.pwn").write_text("main(){}")
            r = self.run_hook("session_start.py", {"cwd": d}, {"CLAUDE_PROJECT_DIR": d})
            self.assertIn("pawn-forge", r.stdout)


if __name__ == "__main__":
    unittest.main()
