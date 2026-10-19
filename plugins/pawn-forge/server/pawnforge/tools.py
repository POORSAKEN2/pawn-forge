"""Tool registry: JSON schemas + dispatch for the MCP server."""
from __future__ import annotations

from pathlib import Path

from . import api, compiler, crashlog, lint, lookup, migrate, project, runner, textdraw

STR = {"type": "string"}
BOOL = {"type": "boolean"}
INT = {"type": "integer"}
STRS = {"type": "array", "items": {"type": "string"}}


def _schema(props: dict, required: list[str] | None = None) -> dict:
    s = {"type": "object", "properties": props, "additionalProperties": False}
    if required:
        s["required"] = required
    return s


def _textdraw_tool(code: str | None = None, file: str | None = None, prefix: str = "TD",
                   target: str = "openmp", ysi_hooks: bool = False, write_to: str | None = None) -> dict:
    if code is None:
        if not file:
            return {"ok": False, "error": "Pass code (the editor export) or file."}
        code = Path(file).expanduser().read_text(encoding="utf-8", errors="replace")
    res = textdraw.convert_textdraws(code, prefix=prefix, target=target, ysi_hooks=ysi_hooks)
    if res.get("ok") and write_to:
        p = Path(write_to).expanduser()
        if p.exists():
            return {**res, "ok": False, "error": f"{p} already exists; choose another path or delete it first."}
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(res["code"], encoding="utf-8")
        res["written"] = str(p)
    return res


TOOLS = [
    {
        "name": "project_info",
        "description": "Inspect a Pawn project: root, main gamemode, includes used, detected libraries (YSI, "
                       "streamer, MySQL, sscanf, Pawn.CMD, dini...), include dirs, target platform (SA-MP vs "
                       "open.mp), server plugins/components, and which compiler is available. Call this first "
                       "in an unfamiliar project.",
        "inputSchema": _schema({"project_dir": STR}, ["project_dir"]),
        "annotations": {"readOnlyHint": True},
        "fn": lambda a: project.project_info(**a),
    },
    {
        "name": "compile",
        "description": "Compile a .pwn file or an inline code snippet with the real Pawn compiler (pawncc 3.10.x, "
                       "or sampctl for pawn.json projects) and return structured diagnostics with fix hints, "
                       "stack usage and the command used. Default output is a throwaway temp .amx; pass "
                       "output='alongside' to keep it. Use after every change to Pawn code and iterate until "
                       "clean. Backslash #include paths are normalised automatically on Linux/macOS.",
        "inputSchema": _schema({
            "file": {**STR, "description": "Path to the .pwn file."},
            "code": {**STR, "description": "Inline source to compile instead of a file."},
            "project_dir": {**STR, "description": "Project root (for include dirs and compiler discovery)."},
            "includes": {**STRS, "description": "Extra include directories."},
            "defines": {"type": "object", "description": "Constants passed as NAME=value."},
            "flags": {**STRS, "description": "Extra compiler flags, e.g. [\"-O1\"]."},
            "output": {**STR, "description": "'temp' (default), 'alongside', or an explicit .amx path."},
            "mode": {"type": "string", "enum": ["auto", "pawncc", "sampctl"]},
            "compat": {**BOOL, "description": "Pass -Z for legacy SA-MP 0.3.7 includes."},
            "default_flags": {**BOOL, "description": "Add -;+ and -(+ (default true)."},
            "normalize_includes": {"type": "string", "enum": ["auto", "always", "never"]},
            "timeout": INT,
        }),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True},
        "fn": lambda a: compiler.compile_pawn(**a),
    },
    {
        "name": "install_compiler",
        "description": "Download the community Pawn compiler (open.mp build 3.10.11 on Windows/Linux, 3.10.10 on "
                       "macOS) from GitHub into the plugin's data directory. Use only when compile reports no "
                       "compiler and the user agrees to the download.",
        "inputSchema": _schema({"version": STR}),
        "annotations": {"readOnlyHint": False, "openWorldHint": True},
        "fn": lambda a: compiler.install_compiler(**a),
    },
    {
        "name": "lint",
        "description": "Static analysis for Pawn: buffer/sizeof mismatches, format specifier vs argument "
                       "mismatches, unsized sscanf strings, SQL injection via format()/%s, legacy MySQL APIs, "
                       "unfreed caches and SQLite results, timer and TextDraw leaks, strtok/dini/zcmd legacy, "
                       "heavy OnPlayerUpdate work, and invalid vehicle/skin/weapon/animation IDs. Scans a file, "
                       "a directory (third-party include dirs skipped by default) or inline code.",
        "inputSchema": _schema({
            "path": STR, "code": STR,
            "rules": {**STRS, "description": "Only run these rule ids (e.g. PF101)."},
            "exclude": {**STRS, "description": "Rule ids to skip."},
            "min_severity": {"type": "string", "enum": ["info", "warning", "error"]},
            "include_third_party": BOOL,
            "max_findings": INT,
        }),
        "annotations": {"readOnlyHint": True},
        "fn": lambda a: lint.lint_paths(**a),
    },
    {
        "name": "lint_rules",
        "description": "List every lint rule with its id, severity, category, title and recommended fix.",
        "inputSchema": _schema({}),
        "annotations": {"readOnlyHint": True},
        "fn": lambda a: {"rules": lint.rules_catalog()},
    },
    {
        "name": "analyze_log",
        "description": "Parse a SA-MP server_log.txt / open.mp log.txt (or pasted text): CrashDetect runtime "
                       "errors with AMX backtraces, server crashes with the suspect plugin, long callbacks, "
                       "missing natives and plugin load failures. Incidents are grouped by root cause with "
                       "counts; pass source_root to attach the source lines around each frame.",
        "inputSchema": _schema({"path": STR, "text": STR, "source_root": STR, "tail_lines": INT,
                                "max_incidents": INT}),
        "annotations": {"readOnlyHint": True},
        "fn": lambda a: crashlog.analyze_log(**a),
    },
    {
        "name": "lookup",
        "description": "Look up and validate in-game IDs from the official open.mp data: vehicle models "
                       "(400-611), weapons (IDs, WEAPON_* constants, slots), skins (0-311 except 74), interiors "
                       "(interior ID + coordinates), animations (library + name) and server limits. Use instead "
                       "of recalling IDs from memory.",
        "inputSchema": _schema({
            "kind": {"type": "string", "enum": list(lookup.KINDS)},
            "query": {"type": ["string", "integer"], "description": "ID, name or keyword."},
            "library": {**STR, "description": "Animation library (kind=animation)."},
            "limit": INT,
        }, ["kind"]),
        "annotations": {"readOnlyHint": True},
        "fn": lambda a: lookup.lookup(**a),
    },
    {
        "name": "api_lookup",
        "description": "Exact native/callback signatures from real include files: open.mp stdlib, Streamer, "
                       "MySQL R41, sscanf2 and Pawn.CMD (bundled), plus the project's own includes when "
                       "project_dir is given. Use name= for one symbol (with open.mp deprecation info) or "
                       "query= to search. Never guess a signature.",
        "inputSchema": _schema({"name": STR, "query": STR, "library": STR, "project_dir": STR, "limit": INT}),
        "annotations": {"readOnlyHint": True},
        "fn": lambda a: api.api_lookup(**a),
    },
    {
        "name": "migrate_openmp",
        "description": "Plan or apply a SA-MP -> open.mp migration for one file: #include <open.mp>, renamed and "
                       "deprecated natives, tagged constants (bool/WEAPON_/TEXT_DRAW_FONT_/Float), callback "
                       "headers (e.g. WEAPON:reason), plugin/component notes. Returns a diff. write='none' "
                       "(default) is a dry run; 'copy' writes <file>.omp.pwn; 'in_place' edits the file after "
                       "saving <file>.samp.bak. Only mechanical, behaviour-preserving edits are applied.",
        "inputSchema": _schema({"file": STR, "code": STR,
                                "write": {"type": "string", "enum": ["none", "copy", "in_place", "return"]}}),
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
        "fn": lambda a: migrate.migrate_openmp(**a),
    },
    {
        "name": "convert_textdraws",
        "description": "Turn a raw TextDraw editor export (TextDrawCreate/CreatePlayerTextDraw + property calls) "
                       "into a clean module: arrays, named index constants, guarded Create/Destroy/Show/Hide "
                       "functions, open.mp names and constants, plus canvas/limit/selectable validation. "
                       "Optionally writes the module to write_to (never overwrites).",
        "inputSchema": _schema({"code": STR, "file": STR, "prefix": STR,
                                "target": {"type": "string", "enum": ["openmp", "samp"]},
                                "ysi_hooks": BOOL, "write_to": STR}),
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
        "fn": lambda a: _textdraw_tool(**a),
    },
    {
        "name": "run_server",
        "description": "Boot a local open.mp server headlessly with a given gamemode (on a free port, not "
                       "announced) and report boot errors, CrashDetect incidents and YSI y_testing results "
                       "(tests/checks/fails, failing tests and assertions). Stops when tests finish, the "
                       "script exits, stop_on matches, or after timeout_s. Requires a local server directory.",
        "inputSchema": _schema({
            "server_dir": STR,
            "script": {**STR, "description": "Gamemode name in gamemodes/ (without .amx)."},
            "amx_path": {**STR, "description": "Compiled .amx to run (copied temporarily into gamemodes/)."},
            "timeout_s": INT,
            "stop_on": {**STR, "description": "Regex; stop once a log line matches."},
            "config": {"type": "object", "description": "Extra open.mp config overrides (key.path: value)."},
        }, ["server_dir"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
        "fn": lambda a: runner.server_run(**a),
    },
]

BY_NAME = {t["name"]: t for t in TOOLS}


def list_tools() -> list[dict]:
    return [{k: v for k, v in t.items() if k != "fn"} for t in TOOLS]


def call_tool(name: str, arguments: dict) -> dict:
    t = BY_NAME.get(name)
    if not t:
        raise KeyError(f"Unknown tool: {name}")
    allowed = set(t["inputSchema"]["properties"])
    unknown = set(arguments) - allowed
    if unknown:
        raise ValueError(f"Unknown argument(s) for {name}: {', '.join(sorted(unknown))}")
    missing = [r for r in t["inputSchema"].get("required", []) if r not in arguments]
    if missing:
        raise ValueError(f"Missing required argument(s) for {name}: {', '.join(missing)}")
    return t["fn"](arguments)
