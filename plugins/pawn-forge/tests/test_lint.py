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

    def test_anticheat_and_ecosystem_rules_and_false_positive_guards(self):
        # PF701: immediate Kick/Ban after SendClientMessage/ShowPlayerDialog fires; timer-delayed or unrelated stays quiet
        bad_kick = 'f(p){ SendClientMessage(p, -1, "Bye"); Kick(p); }'
        bad_return_kick = 'f(p){ SendClientMessage(p, -1, "Bye"); return Kick(p); }'
        bad_ban = 'f(p){ ShowPlayerDialog(p, 1, DIALOG_STYLE_MSGBOX, "Ban", "Bye", "OK", ""); BanEx(p, "reason"); }'
        good_kick = 'f(p){ SendClientMessage(p, -1, "Bye"); SetTimerEx("DelayedKick", 200, false, "i", p); }'
        good_other_player = 'f(admin, target){ SendClientMessage(admin, -1, "Kicked."); Kick(target); }'
        good_standalone_kick = 'public DelayedKick(p){ Kick(p); return 1; }'
        good_different_branch = 'f(p, ok){ if(ok){ SendClientMessage(p, -1, "Welcome"); return 1; } Kick(p); return 1; }'
        good_separated_return = 'f(p){ SendClientMessage(p, -1, "Bye"); return 1; Kick(p); }'
        good_switch_braceless = 'f(p, d){ switch (d) { case 1: SendClientMessage(p, -1, "ok"); case 2: Kick(p); } }'
        good_switch_default = 'f(p, d){ switch (d) { case 1: SendClientMessage(p, -1, "ok"); default: Kick(p); } }'
        good_switch_nested_if = 'f(p, d, x){ switch (d) { case 1: SendClientMessage(p, -1, "ok"); case 2: { if (x) Kick(p); } } }'
        bad_switch_same_case = 'f(p, d){ switch (d) { case 1: { SendClientMessage(p, -1, "bye"); Kick(p); } } }'
        bad_before_switch = 'f(p, d){ SendClientMessage(p, -1, "bye"); switch (d) { case 1: Kick(p); } }'
        self.assertIn("PF701", self.rules(bad_kick))
        self.assertIn("PF701", self.rules(bad_return_kick))
        self.assertIn("PF701", self.rules(bad_ban))
        self.assertEqual(self.rules(good_kick), [])
        self.assertEqual(self.rules(good_other_player), [])
        self.assertEqual(self.rules(good_standalone_kick), [])
        self.assertEqual(self.rules(good_different_branch), [])
        self.assertEqual(self.rules(good_separated_return), [])
        self.assertEqual(self.rules(good_switch_braceless), [])
        self.assertEqual(self.rules(good_switch_default), [])
        self.assertEqual(self.rules(good_switch_nested_if), [])
        self.assertIn("PF701", self.rules(bad_switch_same_case))
        self.assertIn("PF701", self.rules(bad_before_switch))

        # PF702: unguarded strcmp on inputtext fires; isnull/inputtext[0]/strlen guard stays quiet
        bad_cmp = 'public OnDialogResponse(p,d,r,l,inputtext[]){ if(!strcmp(inputtext, "pw")) return 1; return 0; }'
        bad_cmp_rev = 'public OnDialogResponse(p,d,r,l,inputtext[]){ if(strcmp("pw", inputtext) == 0) return 1; return 0; }'
        good_cmp = 'public OnDialogResponse(p,d,r,l,inputtext[]){ if(isnull(inputtext)) return 0; if(!strcmp(inputtext, "pw")) return 1; return 0; }'
        good_cmp_idx0 = 'public OnDialogResponse(p,d,r,l,inputtext[]){ if(!inputtext[0]) return 0; if(!strcmp(inputtext, "pw")) return 1; return 0; }'
        good_cmp_strlen = 'public OnDialogResponse(p,d,r,l,inputtext[]){ if(strlen(inputtext) > 0 && !strcmp(inputtext, "pw")) return 1; return 0; }'
        self.assertIn("PF702", self.rules(bad_cmp))
        self.assertIn("PF702", self.rules(bad_cmp_rev))
        self.assertEqual(self.rules(good_cmp), [])
        self.assertEqual(self.rules(good_cmp_idx0), [])
        self.assertEqual(self.rules(good_cmp_strlen), [])

        # PF703: unguarded weaponid/damagedid/issuerid array index in combat callbacks
        bad_shot = 'new gWep[50]; public OnPlayerWeaponShot(p,w,h,hi,Float:x,Float:y,Float:z){ return gWep[w]; }'
        good_shot = 'new gWep[50]; public OnPlayerWeaponShot(p,w,h,hi,Float:x,Float:y,Float:z){ if(w < 0 || w >= sizeof gWep) return 0; return gWep[w]; }'
        bad_take = 'new gDmg[MAX_PLAYERS]; public OnPlayerTakeDamage(p,i,Float:a,w,b){ gDmg[i]++; return 1; }'
        good_take_inv = 'new gDmg[MAX_PLAYERS]; public OnPlayerTakeDamage(p,i,Float:a,w,b){ if(i != INVALID_PLAYER_ID) gDmg[i]++; return 1; }'
        good_give_conn = 'new gDmg[MAX_PLAYERS]; public OnPlayerGiveDamage(p,d,Float:a,w,b){ if(!IsPlayerConnected(d)) return 0; gDmg[d]++; return 1; }'
        good_own_pid = 'new gShots[MAX_PLAYERS]; public OnPlayerWeaponShot(p,w,h,hi,Float:x,Float:y,Float:z){ gShots[p]++; return 1; }'
        self.assertIn("PF703", self.rules(bad_shot))
        self.assertEqual(self.rules(good_shot), [])
        self.assertIn("PF703", self.rules(bad_take))
        self.assertEqual(self.rules(good_take_inv), [])
        self.assertEqual(self.rules(good_give_conn), [])
        self.assertEqual(self.rules(good_own_pid), [])

        # PF704: RCON format with %s fires; numeric %d or literal stays quiet
        self.assertIn("PF704", self.rules('f(p[]){ new c[64]; format(c, sizeof c, "kick %s", p); SendRconCommand(c); }'))
        self.assertEqual(self.rules('f(id){ new c[64]; format(c, sizeof c, "kick %d", id); SendRconCommand(c); }'), [])
        self.assertEqual(self.rules('f(){ SendRconCommand("gmx"); }'), [])

        # PF801: BS_New/BS_NewCopy without BS_Delete; paired BS_Delete stays quiet
        self.assertIn("PF801", self.rules('f(p){ new BitStream:bs = BS_New(); BS_WriteValue(bs, PR_INT32, p); }'))
        self.assertIn("PF801", self.rules('f(BitStream:src){ new BitStream:bs = BS_NewCopy(src); BS_WriteValue(bs, PR_INT32, 1); }'))
        self.assertEqual(self.rules('f(p){ new BitStream:bs = BS_New(); BS_WriteValue(bs, PR_INT32, p); BS_Delete(bs); }'), [])

        # PF802: IsPlayerInRangeOfPoint inside OnPlayerUpdate fires; outside stays quiet
        self.assertIn("PF802", self.rules('public OnPlayerUpdate(p){ if(IsPlayerInRangeOfPoint(p, 5.0, 0.0, 0.0, 0.0)) return 1; return 1; }'))
        self.assertEqual(self.rules('f(p){ if(IsPlayerInRangeOfPoint(p, 5.0, 0.0, 0.0, 0.0)) return 1; return 0; }'), [])


if __name__ == "__main__":
    unittest.main()
