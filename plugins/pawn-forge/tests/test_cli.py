from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import FIXTURES, PLUGIN


REPO_ROOT = PLUGIN.parent.parent


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

    def test_api_platform_flag_and_stdin_subcommands(self):
        r_samp = self.run_cli(["api", "--name", "SendClientMessage", "--platform", "sa-mp", "--json"])
        self.assertEqual(r_samp.returncode, 0, r_samp.stderr)
        p_samp = json.loads(r_samp.stdout)
        self.assertTrue(p_samp["found"])
        self.assertEqual(p_samp["results"][0]["library"], "samp-stdlib")

        r_dep = self.run_cli(["api", "--name", "GetPlayerPoolSize", "--platform", "samp", "--json"])
        self.assertEqual(r_dep.returncode, 0, r_dep.stderr)
        p_dep = json.loads(r_dep.stdout)
        self.assertTrue(p_dep["found"])
        self.assertNotIn("openmp_deprecation", p_dep)

        r_omp_only = self.run_cli(["api", "--query", "TextDrawColour", "--platform", "sa-mp", "--json"])
        self.assertEqual(r_omp_only.returncode, 0, r_omp_only.stderr)
        self.assertEqual(json.loads(r_omp_only.stdout)["count"], 0)

        r_log = self.run_cli(
            ["analyze-log", "--text", "-", "--json"],
            stdin_text='[debug] Run time error 11: "Divide by zero"\n',
        )
        self.assertEqual(r_log.returncode, 0, r_log.stderr)
        self.assertEqual(json.loads(r_log.stdout)["incidents"][0]["code"], 11)

        r_mig = self.run_cli(
            ["migrate", "--code", "-", "--write", "return", "--json"],
            stdin_text="#include <a_samp>\nmain(){}\n",
        )
        self.assertEqual(r_mig.returncode, 0, r_mig.stderr)
        self.assertIn("<open.mp>", json.loads(r_mig.stdout)["migrated_code"])

        r_td = self.run_cli(
            ["textdraw", "--code", "-", "--prefix", "Hud", "--target", "samp", "--json"],
            stdin_text='new Text:gTd;\ngTd = TextDrawCreate(10.0, 20.0, "Hi");\n',
        )
        self.assertEqual(r_td.returncode, 0, r_td.stderr)
        td_payload = json.loads(r_td.stdout)
        self.assertTrue(td_payload["ok"])
        self.assertEqual(td_payload["globals"], 1)

    def test_human_readable_text_mode_and_error_exit_codes(self):
        for cmd in (
            ["lookup", "vehicle", "infernus"],
            ["lookup", "animation", "WALK_civi", "--library", "ped"],
            ["api", "--name", "mysql_tquery"],
            ["lint-rules"],
            ["info", str(FIXTURES)],
            ["lint", "--code", 'f(){ new a[8]; format(a, 99, "x"); }'],
            ["analyze-log", str(FIXTURES / "server_log.txt")],
            ["migrate", str(FIXTURES / "legacy_samp.pwn"), "--write", "none"],
            ["textdraw", str(FIXTURES / "td_export.pwn"), "--prefix", "Speedo"],
        ):
            with self.subTest(text_cmd=cmd[0]):
                r = self.run_cli(cmd)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertTrue(r.stdout.strip())

        r_comp = self.run_cli(["compile", "/nonexistent/path/gm.pwn", "--json"])
        self.assertEqual(r_comp.returncode, 1)
        self.assertFalse(json.loads(r_comp.stdout)["ok"])

        r_srv = self.run_cli(["run-server", "/nonexistent/server/dir", "--json"])
        self.assertEqual(r_srv.returncode, 1)
        self.assertFalse(json.loads(r_srv.stdout)["ok"])

    def test_mcp_entry_protocol(self):
        env = dict(os.environ, PYTHONPATH=str(PLUGIN / "server"))
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}},
            {"jsonrpc": "2.0", "id": 2, "method": "ping"},
        ]
        p = subprocess.run(
            [sys.executable, "-m", "pawnforge.mcp_entry"],
            input="\n".join(json.dumps(m) for m in msgs) + "\n",
            capture_output=True, text=True, timeout=60, env=env,
        )
        self.assertEqual(p.returncode, 0, p.stderr)
        out = {m["id"]: m for m in map(json.loads, p.stdout.splitlines())}
        self.assertEqual(out[1]["result"]["serverInfo"]["name"], "pawn-forge")
        self.assertEqual(out[2]["result"], {})

    def test_data_pkg_fallback(self):
        from pawnforge import data

        with tempfile.TemporaryDirectory() as d:
            pkg_data = Path(d)
            (pkg_data / "sources.json").write_text('{"test": true}', encoding="utf-8")
            resolved = data._resolve_data_dir(pkg_data)
            self.assertEqual(resolved, pkg_data)
            missing = data._resolve_data_dir(pkg_data / "missing")
            self.assertEqual(missing, Path(data.__file__).resolve().parent.parent / "data")

    @unittest.skipIf(sys.version_info < (3, 11), "tomllib requires Python 3.11+")
    def test_pyproject_toml_structure(self):
        import tomllib

        pyproject = REPO_ROOT / "pyproject.toml"
        self.assertTrue(pyproject.is_file(), f"Missing {pyproject}")
        cfg = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        proj = cfg["project"]
        self.assertEqual(proj["name"], "pawn-forge")
        self.assertEqual(proj["requires-python"], ">=3.8")
        self.assertEqual(proj["dependencies"], [])
        self.assertEqual(proj["scripts"]["pawnforge"], "pawnforge.cli:main")
        self.assertEqual(proj["scripts"]["pawnforge-mcp"], "pawnforge.mcp_entry:main")

        st = cfg["tool"]["setuptools"]
        self.assertEqual(st["package-dir"]["pawnforge"], "plugins/pawn-forge/server/pawnforge")
        self.assertEqual(st["package-dir"]["pawnforge._data"], "plugins/pawn-forge/server/data")
        self.assertEqual(st["package-data"]["pawnforge._data"], ["*.json"])


if __name__ == "__main__":
    unittest.main()
