import unittest

from helpers import FIXTURES, expected_rules

from pawnforge.lint import RULES, lint_paths, lint_source


class FixtureTest(unittest.TestCase):
    def test_every_annotated_line_fires(self):
        path = FIXTURES / "legacy_bad.pwn"
        res = lint_paths(path=str(path))
        got = {}
        for f in res["findings"]:
            got.setdefault(f["line"], set()).add(f["rule"])
        for line, rules in expected_rules(path).items():
            for r in rules:
                self.assertIn(r, got.get(line, set()), f"{r} expected on line {line}, got {got.get(line)}")

    def test_no_findings_on_unannotated_lines_except_file_level(self):
        path = FIXTURES / "legacy_bad.pwn"
        res = lint_paths(path=str(path))
        exp = expected_rules(path)
        file_level = {"PF305", "PF502", "PF506", "PF402"}  # reported on #include / declaration lines
        for f in res["findings"]:
            if f["rule"] in file_level:
                continue
            self.assertIn(f["line"], exp, f"unexpected {f['rule']} on line {f['line']}: {f['message']}")

    def test_all_rules_covered(self):
        res = lint_paths(path=str(FIXTURES / "legacy_bad.pwn"))
        missing = set(RULES) - set(res["by_rule"]) - {"PF406"}
        self.assertEqual(missing, set())


class RuleTest(unittest.TestCase):
    def rules(self, code, **kw):
        return [f["rule"] for f in lint_source(code, **kw)]

    def test_clean_modern_code_is_quiet(self):
        code = '''
#include <open.mp>
#include <a_mysql>
new MySQL:gSQL;
public OnPlayerConnect(playerid)
{
	new name[MAX_PLAYER_NAME + 1], query[128];
	GetPlayerName(playerid, name, sizeof name);
	mysql_format(gSQL, query, sizeof query, "SELECT id FROM players WHERE name = '%e'", name);
	mysql_tquery(gSQL, query, "OnLoaded", "d", playerid);
	SendClientMessage(playerid, -1, "Welcome %s", name);
	CreateVehicle(411, 0.0, 0.0, 3.0, 0.0, -1, -1, 60);
	SetPlayerSkin(playerid, 0);
	GivePlayerWeapon(playerid, WEAPON_DEAGLE, 50);
	ApplyAnimation(playerid, "PED", "WALK_civi", 4.1, false, false, false, false, 0);
	return 1;
}
'''
        found = lint_source(code, min_severity="warning")
        self.assertEqual(found, [], found)

    def test_sizeof_other_buffer(self):
        self.assertIn("PF101", self.rules('f(){ new a[8], b[64]; format(a, sizeof(b), "x"); }'))

    def test_sizeof_without_parens(self):
        self.assertEqual(self.rules('f(){ new a[8]; format(a, sizeof a, "x"); }'), [])

    def test_literal_size_via_define(self):
        self.assertIn("PF102", self.rules('#define LEN 32\nf(){ new a[16]; strcat(a, "x", LEN); }'))

    def test_format_extra_args_is_warning(self):
        f = lint_source('f(){ new a[8]; format(a, sizeof a, "%d", 1, 2); }')
        self.assertEqual([(x["rule"], x["severity"]) for x in f], [("PF104", "warning")])

    def test_format_percent_escape_and_star(self):
        self.assertEqual(self.rules('f(){ new a[8]; format(a, sizeof a, "%% %*d", 5, 1); }'), [])

    def test_settimerex_specifiers(self):
        self.assertEqual(self.rules('f(p){ SetTimerEx("X", 10, false, "ii", p, p); }'), [])
        self.assertIn("PF104", self.rules('f(p){ SetTimerEx("X", 10, false, "i", p, p); }'))

    def test_sscanf_sized_and_quiet_sections(self):
        self.assertEqual(self.rules('f(p[]){ new a, b[8]; sscanf(p, "p<,>is[8]", a, b); }'), [])
        self.assertEqual(self.rules('f(p[]){ new b[8]; sscanf(p, "S(none)[8]", b); }'), [])
        self.assertIn("PF105", self.rules('f(p[]){ new b[8]; sscanf(p, "S(none)", b); }'))

    def test_sqlite_q_is_safe(self):
        self.assertEqual(self.rules('f(){ new q[64], n[8]; format(q, sizeof q, "SELECT * FROM t WHERE n = \'%q\'", n); }'), [])

    def test_sql_in_db_executequery(self):
        self.assertIn("PF201", self.rules('f(DB:d){ new n[8]; DB_FreeResultSet(DB_ExecuteQuery(d, "SELECT * FROM t WHERE n = \'%s\'", n)); }'))

    def test_global_timer_at_init_is_fine(self):
        self.assertEqual(self.rules('public OnGameModeInit(){ SetTimer("T", 1000, true); return 1; }'), [])

    def test_strings_and_comments_ignored(self):
        code = 'f(){ new a[8];\n// format(a, 999, "x");\nprint("format(a, 999, x)"); }'
        self.assertEqual(self.rules(code), [])

    def test_many_static_objects(self):
        code = "public OnGameModeInit()\n{\n" + "\tCreateObject(1337, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0);\n" * 160 + "\treturn 1;\n}\n"
        self.assertIn("PF406", self.rules(code))

    def test_suppression(self):
        code = 'f(){ new a[8];\nformat(a, 99, "x"); // pawnforge-ignore PF102\n}'
        self.assertEqual(self.rules(code), [])
        code = '// pawnforge-ignore-file PF102\nf(){ new a[8];\nformat(a, 99, "x");\n}'
        self.assertEqual(self.rules(code), [])

    def test_rule_filters(self):
        code = 'f(){ new a[8]; format(a, 99, "%d"); }'
        self.assertEqual(self.rules(code, rules=["PF104"]), ["PF104"])
        self.assertNotIn("PF102", self.rules(code, exclude=["PF102"]))


if __name__ == "__main__":
    unittest.main()
