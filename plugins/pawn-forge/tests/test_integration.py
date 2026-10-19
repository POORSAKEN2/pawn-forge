"""Integration tests against the real compiler, real headers and a real open.mp server.

Skipped unless PAWNFORGE_PAWNCC and PAWNFORGE_TEST_INC are set (and PAWNFORGE_TEST_SERVER for server runs).
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from helpers import FIXTURES, TEST_SERVER, have_compiler, inc

from pawnforge.compiler import compile_pawn
from pawnforge.migrate import migrate_openmp
from pawnforge.runner import server_run
from pawnforge.textdraw import convert_textdraws

YSI = ("omp-stdlib", "YSI-Includes", "ysiroot")
SNIPPETS = {
    "mysql_r41.pwn": ("omp-stdlib", "mysqlinc"),
    "pawncmd_sscanf.pwn": ("omp-stdlib", "Pawn.CMD/src", "sscanf"),
    "ysi5.pwn": YSI,
    "streamer.pwn": ("omp-stdlib", "samp-streamer-plugin"),
    "strings_omp.pwn": ("omp-stdlib",),
    "strings_samp.pwn": ("samp-stdlib", "pawn-stdlib"),
}


@unittest.skipUnless(have_compiler(), "set PAWNFORGE_PAWNCC and PAWNFORGE_TEST_INC")
class CompileTest(unittest.TestCase):
    def test_reference_snippets_compile_clean(self):
        for name, incs in SNIPPETS.items():
            with self.subTest(snippet=name):
                r = compile_pawn(file=str(FIXTURES / "doc_snippets" / name), includes=inc(*incs), timeout=600)
                self.assertTrue(r["clean"], [(d["code"], d["line"], d["message"]) for d in r["diagnostics"]] or r)

    def test_diagnostics_are_structured(self):
        r = compile_pawn(code='#include <open.mp>\nmain() { new a[3]; a[3] = 1; undefined(); }\n',
                         includes=inc("omp-stdlib"))
        codes = {d["code"] for d in r["diagnostics"]}
        self.assertEqual(codes, {"032", "017"})
        self.assertTrue(all("hint" in d for d in r["diagnostics"]))
        self.assertEqual(r["diagnostics"][0]["file"], "<snippet>")

    def test_user_error_and_missing_include(self):
        r = compile_pawn(code='#include <open.mp>\n#error Stop here\nmain(){}\n', includes=inc("omp-stdlib"))
        self.assertEqual([(d["code"], d["message"]) for d in r["diagnostics"]], [("user", "Stop here")])
        r = compile_pawn(code='#include <nope_missing>\nmain(){}\n', includes=inc("omp-stdlib"))
        self.assertEqual(r["diagnostics"][0]["code"], "100")
        self.assertIn("next_step", r)

    def test_migration_reaches_clean_openmp_build(self):
        src = FIXTURES / "legacy_samp.pwn"
        before = compile_pawn(file=str(src), includes=inc("samp-stdlib", "pawn-stdlib"))
        self.assertTrue(before["clean"])
        naive = compile_pawn(code=src.read_text().replace("<a_samp>", "<open.mp>"), includes=inc("omp-stdlib"))
        self.assertGreater(naive["errors"] + naive["warnings"], 10)
        migrated = migrate_openmp(file=str(src), write="return")["migrated_code"]
        after = compile_pawn(code=migrated, includes=inc("omp-stdlib"))
        self.assertTrue(after["ok"])
        # Only the deliberately manual GetPlayerPoolSize item remains.
        self.assertEqual([d["code"] for d in after["diagnostics"]], ["234"])

    def test_textdraw_module_compiles(self):
        export = (FIXTURES / "td_export.pwn").read_text()
        for target, header, incs in (("openmp", "#include <open.mp>", ("omp-stdlib",)),
                                     ("samp", "#include <a_samp>", ("samp-stdlib", "pawn-stdlib"))):
            with self.subTest(target=target):
                mod = convert_textdraws(export, prefix="Speedo", target=target)["code"]
                r = compile_pawn(code=f"{header}\n{mod}\nmain(){{}}\n", includes=inc(*incs))
                self.assertTrue(r["clean"], r["diagnostics"])

    def test_ysi_builds_with_backslash_includes(self):
        r = compile_pawn(file=str(FIXTURES / "doc_snippets" / "ysi5.pwn"), includes=inc(*YSI), timeout=600)
        self.assertTrue(r["ok"])
        if os.name != "nt":
            self.assertIn("include_normalization", r)


@unittest.skipUnless(have_compiler() and TEST_SERVER and Path(TEST_SERVER).is_dir(),
                     "set PAWNFORGE_TEST_SERVER to an open.mp server directory")
class ServerTest(unittest.TestCase):
    def test_y_testing_suite(self):
        with tempfile.TemporaryDirectory() as d:
            amx = Path(d, "ytest_economy.amx")
            r = compile_pawn(file=str(FIXTURES / "doc_snippets" / "ytest_economy.pwn"), includes=inc(*YSI),
                             output=str(amx), timeout=600)
            self.assertTrue(r["ok"], r)
            run = server_run(TEST_SERVER, amx_path=str(amx), timeout_s=60)
        self.assertEqual(run["stop_reason"], "tests_finished")
        y = run["y_testing"]
        self.assertEqual((y["tests"], y["fails"]), (2, 1))
        self.assertEqual(y["failed_tests"], [{"test": "PayoutIsCapped", "failed_checks": 1}])
        self.assertTrue(y["assert_failures"])
        self.assertFalse(run["passed"])
        self.assertFalse((Path(TEST_SERVER) / "gamemodes" / "_pawnforge_test.amx").exists())


if __name__ == "__main__":
    unittest.main()
