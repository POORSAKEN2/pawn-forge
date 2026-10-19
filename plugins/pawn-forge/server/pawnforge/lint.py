"""Static analysis for Pawn: buffer safety, SQL injection, resource leaks,
legacy APIs and invalid in-game IDs.

Rules are deliberately conservative: each one fires on a pattern that is a
real defect or a well-established legacy practice, and stays silent when the
analysis cannot be sure (for example when an array size cannot be resolved).

Suppress a finding with a comment:
    // pawnforge-ignore PF101            (same line)
    // pawnforge-ignore-next-line PF101  (line above)
    // pawnforge-ignore-file PF503       (anywhere in the file)
Omit the rule id to suppress every rule on that line.
"""
from __future__ import annotations

import difflib
import os
import re
from dataclasses import dataclass
from pathlib import Path

from . import data
from .source import IDENT, Source, bare_identifier, safe_eval, sizeof_target, string_literal_value

SEVERITY_ORDER = {"info": 0, "warning": 1, "error": 2}


@dataclass(frozen=True)
class Rule:
    id: str
    severity: str
    category: str
    title: str
    fix: str


RULES: dict[str, Rule] = {r.id: r for r in [
    # ---- buffers & strings
    Rule("PF101", "error", "buffer", "Size argument measures a different buffer",
         "Pass sizeof() of the destination buffer itself, e.g. format(dest, sizeof dest, ...)."),
    Rule("PF102", "error", "buffer", "Size argument larger than the destination buffer",
         "Use sizeof(dest) instead of a hard-coded length so the size always matches the declaration."),
    Rule("PF103", "warning", "buffer", "Player-name buffer smaller than MAX_PLAYER_NAME",
         "Declare name buffers as new name[MAX_PLAYER_NAME + 1]; names are up to 24 characters."),
    Rule("PF104", "error", "buffer", "Format specifiers do not match the arguments",
         "Make the number of format specifiers equal the number of arguments passed after the format string."),
    Rule("PF105", "error", "buffer", "sscanf string specifier without a size",
         "Give every string specifier an explicit length matching the destination: s[32], S(default)[32]."),
    Rule("PF106", "warning", "buffer", "Client message longer than 144 characters",
         "Chat messages are truncated at 144 characters. Split the message or shorten it."),
    Rule("PF107", "warning", "buffer", "Very large local array",
         "Large locals live on the AMX stack (16 KB by default). Make the buffer static/global, shrink it, "
         "or raise the limit with #pragma dynamic."),
    # ---- security
    Rule("PF201", "error", "security", "SQL query built with %s (unescaped)",
         "%s inserts input verbatim. MySQL R41: mysql_format with %e for strings. SQLite: use %q inside quotes "
         "(format or DB_ExecuteQuery's own format arguments), e.g. \"... WHERE name = '%q'\"."),
    Rule("PF202", "warning", "security", "mysql_format inserts a quoted value with %s instead of %e",
         "Use %e for every quoted value: mysql_format(h, q, sizeof q, \"... WHERE name = '%e'\", name). %s is only "
         "safe for values your code fully controls (e.g. a hex hash), and %e costs nothing there either."),
    Rule("PF203", "warning", "security", "Weak password hashing",
         "Hash passwords with bcrypt (samp-bcrypt plugin) using a per-user salt; never with udb_hash, "
         "Whirlpool, MD5 or SHA256_PassHash."),
    # ---- databases & storage
    Rule("PF301", "warning", "database", "Legacy (pre-R40) MySQL plugin API",
         "Port to MySQL R41: mysql_tquery + callback, cache_get_value_name*/cache_get_row_count."),
    Rule("PF302", "warning", "database", "Blocking mysql_query on the server thread",
         "Use mysql_tquery with a callback; mysql_query blocks the whole server until the database answers."),
    Rule("PF303", "error", "database", "Cache from mysql_query is never deleted",
         "Call cache_delete(result) once you are done with the result, on every return path."),
    Rule("PF304", "warning", "database", "SQLite result set not freed",
         "Free every result with DB_FreeResultSet (db_free_result on SA-MP), including results of "
         "UPDATE/INSERT queries."),
    Rule("PF305", "warning", "database", "File-based account storage (dini/dfile/dudb/DOF2/y_ini)",
         "Move persistent data to SQLite (built in) or MySQL R41. See the modernize-storage skill."),
    # ---- lifecycle & leaks
    Rule("PF401", "warning", "lifecycle", "Repeating timer ID discarded",
         "Store the timer ID so it can be stopped with KillTimer (e.g. on disconnect), or use a y_timers ptask."),
    Rule("PF402", "info", "lifecycle", "Timer ID stored but never killed",
         "Call KillTimer on the stored ID when the owner goes away (OnPlayerDisconnect, script exit)."),
    Rule("PF403", "warning", "lifecycle", "Global TextDraw created in a repeating callback without TextDrawDestroy",
         "Create global TextDraws once in OnGameModeInit (2048 limit server-wide) or destroy them when done."),
    Rule("PF404", "warning", "lifecycle", "Player TextDraw created in a repeating callback without PlayerTextDrawDestroy",
         "Create per-player TextDraws once (e.g. OnPlayerConnect) and reuse them; destroy before re-creating "
         "(256 per player)."),
    Rule("PF405", "info", "lifecycle", "Entity created in a repeating callback with no matching destroy in the file",
         "Destroy entities created per spawn/command/timer, or create them once; pools are finite."),
    Rule("PF406", "info", "performance", "Many static CreateObject calls",
         "Static objects are limited (1000 in SA-MP). Use the Streamer plugin's CreateDynamicObject for maps."),
    # ---- performance & modernization
    Rule("PF501", "warning", "modernize", "strtok/strcmp command parsing",
         "Use Pawn.CMD (cmd:name(playerid, params[])) or y_commands with sscanf for argument parsing."),
    Rule("PF502", "info", "modernize", "dcmd/zcmd-era command processor",
         "Pawn.CMD is a drop-in, faster processor (cmd:/CMD: syntax); y_commands if you use YSI."),
    Rule("PF503", "info", "modernize", "Loop over every player slot",
         "Iterate connected players only: foreach (new i : Player) with y_iterate (or open.mp's foreach)."),
    Rule("PF504", "warning", "performance", "Expensive work inside OnPlayerUpdate",
         "OnPlayerUpdate runs ~30 times per second per player. Move queries, file I/O, loops and messages "
         "to timers or event callbacks."),
    Rule("PF505", "info", "modernize", "Magic number dialog ID",
         "Name dialog IDs with an enum (or use y_dialog / easyDialog) to avoid ID collisions between systems."),
    Rule("PF506", "info", "modernize", "SA-MP include on an open.mp-capable script",
         "open.mp servers use #include <open.mp>; run the migrate_openmp tool for the full change list."),
    # ---- ID validation
    Rule("PF601", "error", "validation", "Invalid vehicle model ID",
         "Vehicle models are 400-611. Use the lookup tool (kind=vehicle) to find the right ID."),
    Rule("PF602", "error", "validation", "Invalid skin ID",
         "Skins are 0-311 except 74. Use the lookup tool (kind=skin)."),
    Rule("PF603", "error", "validation", "Weapon ID that cannot be given",
         "Givable weapons are 0-18 and 22-46. Use the WEAPON_* constants or the lookup tool (kind=weapon)."),
    Rule("PF604", "error", "validation", "Unknown animation",
         "Check the library and animation name with the lookup tool (kind=animation)."),
]}

# Natives taking (destination, size) - argument indices.
SIZED_DEST = {
    "format": (0, 1), "strcat": (0, 2), "strmid": (0, 4), "strins": (0, 3), "strpack": (0, 2),
    "strunpack": (0, 2), "strcopy": (0, 2), "GetPlayerName": (1, 2), "GetPlayerIp": (1, 2), "gpci": (1, 2),
    "GetPVarString": (2, 3), "GetSVarString": (1, 2), "fread": (1, 2), "mysql_format": (1, 2),
    "mysql_escape_string": (1, 2), "cache_get_value_name": (2, 3), "cache_get_value_index": (2, 3),
    "cache_get_field_name": (1, 2), "DB_GetFieldString": (2, 3), "DB_GetFieldStringByName": (2, 3),
    "db_get_field": (2, 3), "db_get_field_assoc": (2, 3), "GetConsoleVarAsString": (1, 2),
    "GetServerVarAsString": (1, 2), "GetPlayerVersion": (1, 2), "GetWeaponName": (1, 2),
    "GetPlayerNetworkStats": (1, 2), "GetNetworkStats": (0, 1), "NetStats_GetIpPort": (1, 2),
}
# (format-string index, kind): kind "printf" counts %-specifiers, "spec" counts specifier letters.
FORMATTERS = {
    "format": (2, "printf"), "printf": (0, "printf"), "mysql_format": (3, "printf"),
    "SendClientMessage": (2, "printf_opt"), "SendClientMessageToAll": (1, "printf_opt"),
    "GameTextForPlayer": (1, "printf_opt_tail2"), "DB_ExecuteQuery": (1, "printf_opt"), "SetTimerEx": (3, "spec"), "CallLocalFunction": (1, "spec"),
    "CallRemoteFunction": (1, "spec"), "mysql_tquery": (3, "spec"), "mysql_pquery": (3, "spec"),
}
LEGACY_MYSQL = {
    "mysql_function_query", "cache_get_data", "cache_get_field_content", "cache_get_field_content_int",
    "cache_get_field_content_float", "cache_get_row", "cache_get_row_int", "cache_get_row_float",
    "cache_get_row_count_ex", "mysql_real_escape_string", "mysql_store_result", "mysql_free_result",
    "mysql_fetch_row", "mysql_fetch_row_format", "mysql_fetch_field_row", "mysql_retrieve_row",
    "mysql_num_rows", "mysql_fetch_int", "mysql_fetch_float", "mysql_data_seek", "mysql_reconnect",
}
FILE_STORAGE = re.compile(r"\b(dini_\w+|dfile_\w+|udb_\w+|DOF2_\w+|INI_ParseFile|INI_Open|INI_WriteInt|"
                          r"INI_WriteString|INI_Close|INI_SetTag|INI_Int|INI_String|INI_Float)\s*\(")
WEAK_HASH = re.compile(r"\b(udb_hash|SHA256_PassHash|WP_Hash|Whirlpool|MD5_Hash|md5|num_hash)\s*\(")
REPEATING_CALLBACKS = {
    "OnPlayerConnect", "OnPlayerSpawn", "OnPlayerRequestClass", "OnPlayerStateChange", "OnPlayerEnterVehicle",
    "OnPlayerExitVehicle", "OnDialogResponse", "OnPlayerCommandText", "OnPlayerText", "OnPlayerKeyStateChange",
    "OnPlayerUpdate", "OnPlayerDeath", "OnPlayerEnterCheckpoint", "OnPlayerEnterRaceCheckpoint",
    "OnPlayerClickTextDraw", "OnPlayerClickPlayerTextDraw", "OnPlayerPickUpPickup", "OnPlayerSelectedMenuRow",
}
SQL_RE = re.compile(r"(?i)\b(select\b.+\bfrom|insert\s+into|update\s+\S+\s+set|delete\s+from|replace\s+into)\b")
PRINTF_SPEC = re.compile(r"%(?:%|[-+ 0#]*(\*|\d+)?(?:\.(\*|\d+))?([a-zA-Z]))")


def _printf_count(fmt: str) -> int:
    n = 0
    for m in PRINTF_SPEC.finditer(fmt):
        if m.group(0) == "%%":
            continue
        n += 1 + (m.group(1) == "*") + (m.group(2) == "*")
    return n


def _spec_count(spec: str) -> int:
    # SetTimerEx / CallLocalFunction / mysql_tquery specifier strings: one letter per argument.
    # Array specifiers ('a'/'A') are followed by their size argument.
    n = 0
    for ch in spec:
        if ch.isalpha():
            n += 1
    return n


def _sscanf_unsized(fmt: str) -> list[str]:
    """Return offending string specifiers in an sscanf format string."""
    bad, i, n = [], 0, len(fmt)
    depth_angle = 0
    while i < n:
        c = fmt[i]
        if c == "'":
            j = fmt.find("'", i + 1)
            i = n if j < 0 else j + 1
            continue
        if c == "<":
            depth_angle += 1
        elif c == ">":
            depth_angle = max(0, depth_angle - 1)
        elif depth_angle == 0 and c in "sSzZ":
            j = i + 1
            if c in "SZ" and j < n and fmt[j] == "(":
                k = fmt.find(")", j)
                j = n if k < 0 else k + 1
            if j >= n or fmt[j] != "[":
                bad.append(fmt[i:j] or c)
            i = j
            continue
        elif c in "pPaAeE" and i + 1 < n and fmt[i + 1] == "<":
            # Delimiter / array / enum blocks: skip their type parameter.
            k = fmt.find(">", i + 1)
            i = n if k < 0 else k + 1
            if c in "aA" and i < n and fmt[i] == "[":
                k = fmt.find("]", i)
                i = n if k < 0 else k + 1
            continue
        i += 1
    return bad


def _int_literal(arg: str | None) -> int | None:
    if arg is None:
        return None
    m = re.fullmatch(r"\s*(-?\d+)\s*", arg)
    return int(m.group(1)) if m else None


class Linter:
    def __init__(self, src: Source, enabled: set[str]):
        self.s = src
        self.enabled = enabled
        self.findings: list[dict] = []
        self._suppress_file, self._suppress_lines = self._suppressions()

    # ------------------------------------------------------------------ plumbing
    def _suppressions(self):
        file_rules: set[str] = set()
        line_rules: dict[int, set[str]] = {}
        for i, line in enumerate(self.s.text.split("\n"), start=1):
            for m in re.finditer(r"pawnforge-ignore(-next-line|-file)?\b([ \t,A-Z0-9]*)", line):
                ids = set(re.findall(r"PF\d{3}", m.group(2))) or {"*"}
                if m.group(1) == "-file":
                    file_rules |= ids
                elif m.group(1) == "-next-line":
                    line_rules.setdefault(i + 1, set()).update(ids)
                else:
                    line_rules.setdefault(i, set()).update(ids)
        return file_rules, line_rules

    def add(self, rule_id: str, offset: int, message: str, **extra):
        if rule_id not in self.enabled:
            return
        line = self.s.line_of(offset)
        if {"*", rule_id} & self._suppress_file:
            return
        if {"*", rule_id} & self._suppress_lines.get(line, set()):
            return
        r = RULES[rule_id]
        f = {
            "rule": rule_id,
            "severity": extra.pop("severity", r.severity),
            "category": r.category,
            "title": r.title,
            "message": message,
            "file": self.s.path,
            "line": line,
            "col": self.s.col_of(offset),
            "source": self.s.line_text(line).strip()[:240],
            "fix": extra.pop("fix", r.fix),
        }
        fn = self.s.function_at(offset)
        if fn:
            f["function"] = fn.name
        f.update(extra)
        self.findings.append(f)

    def run(self) -> list[dict]:
        for name in sorted(n for n in dir(self) if n.startswith("check_")):
            getattr(self, name)()
        self.findings.sort(key=lambda f: (f["line"], f["col"], f["rule"]))
        return self.findings

    def _repeating(self, offset: int) -> bool:
        fn = self.s.function_at(offset)
        if not fn:
            return False
        return fn.kind in ("command", "dialog", "timer") or fn.name.split(":")[-1] in REPEATING_CALLBACKS

    def _statement_context(self, call_start: int) -> str:
        """Text before the call on the same statement (to see if the result is used)."""
        t = self.s.masked
        j = call_start - 1
        while j >= 0 and t[j] not in ";{}":
            j -= 1
        return t[j + 1:call_start].strip()

    # ------------------------------------------------------------------ buffers
    def check_sized_destinations(self):
        names = "|".join(map(re.escape, SIZED_DEST))
        for c in self.s.calls(names):
            di, si = SIZED_DEST[c.name]
            dest = bare_identifier(c.arg(self.s, di))
            size_arg = c.arg(self.s, si)
            if not dest or size_arg is None:
                continue
            target = sizeof_target(size_arg)
            if target and target != dest:
                self.add("PF101", c.start, f"{c.name} writes into '{dest}' but limits the size with sizeof({target}).",
                         fix=f"Use sizeof({dest}).")
                continue
            declared = self.s.array_size(dest, c.start)
            if declared is None:
                continue
            given = None if target else safe_eval(size_arg, self.s.defines)
            if given is not None and given > declared:
                self.add("PF102", c.start,
                         f"{c.name} is told '{dest}' holds {given} cells but it is declared with {declared}.",
                         fix=f"Use sizeof({dest}) (or sizeof {dest}).")
                continue
            if c.name == "GetPlayerName" and declared < 24:
                self.add("PF103", c.start,
                         f"'{dest}' holds {declared} cells, less than MAX_PLAYER_NAME (24): longer names are truncated.")

    def check_format_arguments(self):
        names = "|".join(map(re.escape, FORMATTERS))
        for c in self.s.calls(names):
            fi, kind = FORMATTERS[c.name]
            if c.close_paren < 0 or fi >= len(c.args):
                continue
            lit = string_literal_value(c.arg(self.s, fi) or "")
            if lit is None:
                continue
            extra = len(c.args) - fi - 1
            if kind == "printf_opt_tail2":
                extra -= 2  # GameTextForPlayer(playerid, fmt, time, style, ...)
            if kind.startswith("printf_opt") and extra <= 0:
                continue  # plain message without formatting arguments
            want = _spec_count(lit) if kind == "spec" else _printf_count(lit)
            if want == extra:
                continue
            what = "specifier letters" if kind == "spec" else "format specifiers"
            sev = "error" if want > extra else "warning"
            self.add("PF104", c.start,
                     f"{c.name} has {want} {what} in \"{lit[:60]}\" but {extra} argument(s) follow.",
                     severity=sev)

    def check_sscanf(self):
        for c in self.s.calls(r"sscanf|unformat"):
            lit = string_literal_value(c.arg(self.s, 1) or "")
            if lit is None:
                continue
            bad = _sscanf_unsized(lit)
            if bad:
                self.add("PF105", c.start, f"sscanf format \"{lit}\" has string specifier(s) without a size: "
                                           f"{', '.join(bad)}.")

    def check_message_length(self):
        for c in self.s.calls(r"SendClientMessage|SendClientMessageToAll|SendPlayerMessageToPlayer|SendPlayerMessageToAll"):
            idx = {"SendClientMessage": 2, "SendClientMessageToAll": 1,
                   "SendPlayerMessageToPlayer": 2, "SendPlayerMessageToAll": 1}[c.name]
            lit = string_literal_value(c.arg(self.s, idx) or "")
            if lit is None:
                continue
            # Escape sequences count as one character each; colour embeds {RRGGBB} do count.
            length = len(re.sub(r"\\.", "_", lit))
            if length > 144:
                self.add("PF106", c.start, f"Message literal is {length} characters; the client shows at most 144.")

    def check_large_locals(self):
        for d in self.s.arrays:
            if not d.local or d.static:
                continue
            cells = 1
            for sz in d.sizes:
                if sz is None:
                    cells = None
                    break
                cells *= sz
            if cells and cells >= 4096:
                self.add("PF107", d.offset, f"Local array '{d.name}' uses {cells} cells ({cells * 4} bytes) of stack.")

    # ------------------------------------------------------------------ security
    def check_sql_format(self):
        for c in self.s.calls(r"format|strcat|DB_ExecuteQuery"):
            idx = {"format": 2, "strcat": 1, "DB_ExecuteQuery": 1}[c.name]
            lit = string_literal_value(c.arg(self.s, idx) or "")
            if lit and SQL_RE.search(lit) and re.search(r"%(?:[-0-9.]*)s", lit):
                self.add("PF201", c.start, f"SQL statement assembled with {c.name} and %s: input is inserted unescaped.")
        for c in self.s.calls(r"mysql_format"):
            lit = string_literal_value(c.arg(self.s, 3) or "")
            if lit and re.search(r"""['"`]%s|%s['"`]""", lit):
                self.add("PF202", c.start, "mysql_format uses %s inside quotes; the value is not escaped.")

    def check_weak_hash(self):
        for m in WEAK_HASH.finditer(self.s.masked):
            if re.search(r"\b(native|forward|stock|public)\s+$", self.s.masked[max(0, m.start() - 20):m.start()]):
                continue
            self.add("PF203", m.start(), f"{m.group(1)} is not suitable for password storage.")

    # ------------------------------------------------------------------ databases
    def check_legacy_mysql(self):
        for c in self.s.calls("|".join(sorted(LEGACY_MYSQL))):
            self.add("PF301", c.start, f"{c.name} belongs to the pre-R40 MySQL plugin API.")

    def check_mysql_query(self):
        for c in self.s.calls(r"mysql_query"):
            if len(c.args) >= 2 and (c.arg(self.s, 0) or "").startswith(("\"", "!")):
                continue  # R7-era signature handled by PF301 context; skip guesswork
            self.add("PF302", c.start, "mysql_query blocks the server thread until the query completes.")
            ctx = self._statement_context(c.start)
            m = re.search(rf"({IDENT}(?:\[[^\]]*\])?)\s*=\s*$", ctx)
            fn = self.s.function_at(c.start)
            use_cache = c.arg(self.s, 2)
            if use_cache is not None and use_cache.strip() in ("false", "0"):
                continue
            if m and fn:
                var = re.match(IDENT, m.group(1)).group(0)
                body = self.s.masked[fn.body_start:fn.body_end]
                if not re.search(rf"\bcache_delete\s*\(\s*{re.escape(var)}\b", body):
                    self.add("PF303", c.start, f"Cache '{var}' from mysql_query is never passed to cache_delete in {fn.name}.")
            elif not m and not ctx.endswith(("return", "(", ",")):
                self.add("PF303", c.start, "mysql_query result discarded: the cache it creates is never deleted.",
                         fix="Pass use_cache=false for statements without results, or store and cache_delete the result.")

    def check_sqlite_results(self):
        for c in self.s.calls(r"db_query|DB_ExecuteQuery"):
            ctx = self._statement_context(c.start)
            fn = self.s.function_at(c.start)
            if re.search(r"\b(db_free_result|DB_FreeResultSet)\s*\(\s*$", ctx):
                continue
            m = re.search(rf"({IDENT})\s*=\s*$", ctx) or re.search(rf"\bnew\s+(?:{IDENT}:)?({IDENT})\s*=\s*$", ctx)
            if m and fn:
                var = m.group(1)
                body = self.s.masked[fn.body_start:fn.body_end]
                if not re.search(rf"\b(db_free_result|DB_FreeResultSet)\s*\(\s*{re.escape(var)}\b", body) \
                        and not re.search(rf"\breturn\s+{re.escape(var)}\b", body):
                    self.add("PF304", c.start, f"Result '{var}' from {c.name} is never freed in {fn.name}.")
            elif not m and ctx in ("",):
                self.add("PF304", c.start, f"Result of {c.name} is discarded without being freed.",
                         fix=f"Wrap it: DB_FreeResultSet({c.name}(...)); (db_free_result on SA-MP).")

    def check_file_storage(self):
        seen = 0
        for inc in self.s.includes():
            if inc.lower() in ("dini", "dini2", "dfile", "dudb", "dutils", "dof2", "ysi\\y_ini", "ysi/y_ini",
                               "ysi_storage\\y_ini", "ysi_storage/y_ini"):
                m = re.search(rf"#\s*include\s*[<\"]{re.escape(inc)}", self.s.nocomment)
                if m:
                    is_yini = "y_ini" in inc.lower()
                    self.add("PF305", m.start(), f"#include <{inc}>: file-based storage library.",
                             severity="info" if is_yini else "warning")
                    seen += 1
        if seen:
            return
        m = FILE_STORAGE.search(self.s.masked)
        if m:
            n = len(FILE_STORAGE.findall(self.s.masked))
            self.add("PF305", m.start(), f"{m.group(1)} and {n - 1} other file-storage call(s).")

    # ------------------------------------------------------------------ lifecycle
    def check_timers(self):
        stored: list[tuple[str, int]] = []
        for c in self.s.calls(r"SetTimer|SetTimerEx"):
            rep = c.arg(self.s, 2)
            repeating = rep is not None and rep.strip() in ("true", "1")
            ctx = self._statement_context(c.start)
            m = re.search(rf"({IDENT})(?:\[[^\]]*\])*\s*=\s*$", ctx)
            if m:
                stored.append((m.group(1), c.start))
            elif repeating and (ctx == "" or ctx.endswith(("else", ")"))) and self._repeating(c.start):
                # A global repeating timer started once at init is fine; one started per
                # connection/spawn/command piles up because nothing can ever stop it.
                fn = self.s.function_at(c.start)
                self.add("PF401", c.start, f"{c.name} starts a repeating timer in {fn.name} and throws its ID away; "
                                           "each call adds another timer that can never be stopped.")
        if not stored:
            return
        kills = " ".join(m.group(0) for m in re.finditer(r"\bKillTimer\s*\([^;]*", self.s.masked))
        for var, off in stored:
            if not re.search(rf"\b{re.escape(var)}\b", kills):
                self.add("PF402", off, f"Timer ID stored in '{var}' is never passed to KillTimer in this file.")

    def check_textdraw_leaks(self):
        masked = self.s.masked
        has_td_destroy = re.search(r"\bTextDrawDestroy\s*\(", masked)
        has_ptd_destroy = re.search(r"\bPlayerTextDrawDestroy\s*\(", masked)
        for c in self.s.calls(r"TextDrawCreate"):
            if not has_td_destroy and self._repeating(c.start):
                self.add("PF403", c.start, "TextDrawCreate runs on every call of this callback and nothing destroys it.")
        for c in self.s.calls(r"CreatePlayerTextDraw"):
            fn = self.s.function_at(c.start)
            if fn and fn.name.split(":")[-1] == "OnPlayerConnect":
                continue  # once per connection; freed automatically on disconnect
            if not has_ptd_destroy and self._repeating(c.start):
                self.add("PF404", c.start, "CreatePlayerTextDraw runs on every call of this callback and nothing destroys it.")

    def check_entity_leaks(self):
        pairs = {
            r"CreateDynamic(Object|Pickup|CP|RaceCP|MapIcon|3DTextLabel|Area\w*|Actor|Circle|Rectangle|Sphere|Cube|Cylinder|Polygon)":
                r"DestroyDynamic\w*|DestroyAllDynamic\w*",
            r"Create3DTextLabel": r"Delete3DTextLabel",
            r"CreatePlayer3DTextLabel": r"DeletePlayer3DTextLabel",
            r"CreatePickup": r"DestroyPickup",
            r"CreateObject": r"DestroyObject",
            r"CreateVehicle": r"DestroyVehicle",
            r"CreateActor": r"DestroyActor",
        }
        for create, destroy in pairs.items():
            if re.search(rf"\b(?:{destroy})\s*\(", self.s.masked):
                continue
            for c in self.s.calls(create):
                if self._repeating(c.start):
                    self.add("PF405", c.start, f"{c.name} runs on every call of this callback and this file never destroys it.")
        n = len(self.s.calls(r"CreateObject"))
        if n >= 150:
            first = self.s.calls(r"CreateObject")[0]
            self.add("PF406", first.start, f"{n} CreateObject calls in this file.")

    # ------------------------------------------------------------------ modernization
    def check_commands(self):
        for c in self.s.calls(r"strtok"):
            self.add("PF501", c.start, "strtok-based command parsing.")
            break
        for c in self.s.calls(r"strcmp"):
            a0, a1 = c.arg(self.s, 0) or "", c.arg(self.s, 1) or ""
            if re.match(r'\s*"/', a1) or re.match(r'\s*"/', a0):
                fn = self.s.function_at(c.start)
                self.add("PF501", c.start, "Command matched with strcmp"
                         + (f" in {fn.name}" if fn else "") + ".")
                break
        m = re.search(r"\bdcmd\s*\(", self.s.masked)
        if m:
            self.add("PF502", m.start(), "dcmd macro command processor.")
        for inc in self.s.includes():
            if inc.lower() in ("zcmd", "izcmd", "dcmd"):
                m = re.search(rf"#\s*include\s*[<\"]{re.escape(inc)}", self.s.nocomment)
                if m:
                    self.add("PF502", m.start(), f"#include <{inc}>.")

    def check_player_loops(self):
        pat = re.compile(r"\bfor\s*\(\s*(?:new\s+)?(\w+)\s*=\s*0\s*(?:,[^;]*)?;\s*\1\s*"
                         r"(<\s*MAX_PLAYERS\b|<=?\s*GetMaxPlayers\s*\(\s*\)|<=?\s*GetPlayerPoolSize\s*\(\s*\))")
        pool = re.compile(r"\bfor\s*\(\s*new\s+\w+\s*=\s*0\s*,\s*\w+\s*=\s*(GetPlayerPoolSize|GetMaxPlayers)\s*\(\s*\)")
        seen = set()
        for m in list(pat.finditer(self.s.masked)) + list(pool.finditer(self.s.masked)):
            if m.start() in seen:
                continue
            seen.add(m.start())
            self.add("PF503", m.start(), f"Loop visits every player slot ({m.group(2 if m.re is pat else 1).strip()}).")

    def check_onplayerupdate(self):
        for fn in self.s.functions:
            if fn.name != "OnPlayerUpdate":
                continue
            body = self.s.masked[fn.body_start:fn.body_end]
            heavy = re.search(r"\b(mysql_\w*query|db_query|DB_ExecuteQuery|fopen|fwrite|fread|"
                              r"dini_\w+|INI_\w+|SendClientMessageToAll|GameTextForAll)\s*\(", body)
            loop = re.search(r"\bfor\s*\([^;]*;\s*\w+\s*<\s*MAX_PLAYERS|\bforeach\s*\(", body)
            hit = heavy or loop
            if hit:
                what = hit.group(1) if heavy else "a loop over players"
                self.add("PF504", fn.body_start + hit.start(), f"OnPlayerUpdate calls {what}.")

    def check_dialog_ids(self):
        for c in self.s.calls(r"ShowPlayerDialog"):
            v = _int_literal(c.arg(self.s, 1))
            if v is not None and v >= 0:
                self.add("PF505", c.start, f"ShowPlayerDialog uses literal dialog ID {v}.")

    def check_samp_include(self):
        incs = [i.lower() for i in self.s.includes()]
        if "a_samp" in incs and "open.mp" not in incs:
            m = re.search(r"#\s*include\s*<a_samp>", self.s.nocomment)
            if m:
                self.add("PF506", m.start(), "#include <a_samp>.")

    # ------------------------------------------------------------------ validation
    def check_ids(self):
        vids, skins, weapons = data.vehicle_ids(), data.skin_ids(), data.givable_weapon_ids()
        for c in self.s.calls(r"CreateVehicle|AddStaticVehicle|AddStaticVehicleEx|CreateDynamicVehicle"):
            v = _int_literal(c.arg(self.s, 0))
            if v is not None and v not in vids:
                self.add("PF601", c.start, f"{c.name} uses vehicle model {v}, which does not exist.")
        skin_arg = {"SetPlayerSkin": 1, "AddPlayerClass": 0, "AddPlayerClassEx": 1, "SetSpawnInfo": 2,
                    "CreateActor": 0, "CreateDynamicActor": 0}
        for c in self.s.calls("|".join(skin_arg)):
            v = _int_literal(c.arg(self.s, skin_arg[c.name]))
            if v is not None and v not in skins:
                self.add("PF602", c.start, f"{c.name} uses skin {v}, which is not a valid skin.")
        for c in self.s.calls(r"GivePlayerWeapon"):
            v = _int_literal(c.arg(self.s, 1))
            if v is not None and v not in weapons:
                self.add("PF603", c.start, f"GivePlayerWeapon uses weapon {v}, which cannot be given to a player.")
        idx = data.animation_index()
        libs = data.animation_libraries()
        for c in self.s.calls(r"ApplyAnimation|ApplyActorAnimation|ApplyDynamicActorAnimation"):
            lib = string_literal_value(c.arg(self.s, 1) or "")
            name = string_literal_value(c.arg(self.s, 2) or "")
            if lib is None or name is None:
                continue
            if lib.upper() not in libs:
                sug = difflib.get_close_matches(lib.upper(), libs, n=3)
                self.add("PF604", c.start, f"Animation library \"{lib}\" does not exist."
                         + (f" Did you mean {', '.join(sug)}?" if sug else ""))
            elif (lib.upper(), name.upper()) not in idx:
                names = [n for (l, n) in idx if l == lib.upper()]
                sug = difflib.get_close_matches(name.upper(), names, n=3)
                self.add("PF604", c.start, f"Animation \"{name}\" is not in library \"{lib}\"."
                         + (f" Did you mean {', '.join(sug)}?" if sug else ""))


# ---------------------------------------------------------------------- entry points
def lint_source(text: str, path: str = "<memory>", rules: list[str] | None = None,
                exclude: list[str] | None = None, min_severity: str = "info") -> list[dict]:
    enabled = set(rules) if rules else set(RULES)
    enabled -= set(exclude or [])
    src = Source(text, path=path)
    findings = Linter(src, enabled).run()
    floor = SEVERITY_ORDER.get(min_severity, 0)
    return [f for f in findings if SEVERITY_ORDER[f["severity"]] >= floor]


THIRD_PARTY_DIRS = {"dependencies", "include", "includes", "qawno", "pawno", "plugins", "components", ".git"}


def lint_paths(path: str | None = None, code: str | None = None, rules: list[str] | None = None,
               exclude: list[str] | None = None, min_severity: str = "info", include_third_party: bool = False,
               max_findings: int = 300) -> dict:
    files: list[Path] = []
    findings: list[dict] = []
    if code is not None:
        findings = lint_source(code, "<snippet>", rules, exclude, min_severity)
    elif path:
        p = Path(path).expanduser().resolve()
        if p.is_file():
            files = [p]
        elif p.is_dir():
            for root, dirs, fns in os.walk(p):
                dirs[:] = [d for d in dirs if include_third_party or d.lower() not in THIRD_PARTY_DIRS]
                for fn in fns:
                    if fn.lower().endswith((".pwn", ".inc", ".p")):
                        files.append(Path(root) / fn)
        else:
            return {"ok": False, "error": f"Path not found: {p}"}
        for f in sorted(files):
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                findings.append({"rule": "IO", "severity": "warning", "file": str(f), "line": 0, "message": str(exc)})
                continue
            findings.extend(lint_source(text, str(f), rules, exclude, min_severity))
    else:
        return {"ok": False, "error": "Pass path or code."}
    summary: dict[str, int] = {"error": 0, "warning": 0, "info": 0}
    by_rule: dict[str, int] = {}
    for f in findings:
        summary[f["severity"]] = summary.get(f["severity"], 0) + 1
        by_rule[f["rule"]] = by_rule.get(f["rule"], 0) + 1
    findings.sort(key=lambda f: (-SEVERITY_ORDER.get(f["severity"], 0), f["file"], f["line"]))
    return {
        "ok": True,
        "files_scanned": len(files) if code is None else 1,
        "summary": summary,
        "by_rule": dict(sorted(by_rule.items())),
        "findings": findings[:max_findings],
        "truncated": len(findings) > max_findings,
    }


def rules_catalog() -> list[dict]:
    return [{"id": r.id, "severity": r.severity, "category": r.category, "title": r.title, "fix": r.fix}
            for r in RULES.values()]
