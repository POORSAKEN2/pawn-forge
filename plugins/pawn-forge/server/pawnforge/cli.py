"""Zero-dependency standalone CLI for pawn-forge.

Maps every MCP tool in `pawnforge.tools` 1:1 to a CLI subcommand.
Standard library only: requires Python 3.8+ and nothing else.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from . import __version__, lookup
from .tools import call_tool


def _parse_kv_pairs(pairs: list[str] | None, *, coerce: bool = False) -> dict[str, Any] | None:
    if not pairs:
        return None
    out: dict[str, Any] = {}
    for item in pairs:
        key, sep, val = item.partition("=")
        key = key.strip()
        if not key:
            raise ValueError(f"Invalid key=value entry: {item!r}")
        if not sep:
            out[key] = ""
            continue
        if coerce:
            low = val.strip().lower()
            if low == "true":
                out[key] = True
                continue
            if low == "false":
                out[key] = False
                continue
            try:
                out[key] = int(val)
                continue
            except ValueError:
                pass
        out[key] = val
    return out


def _read_stdin_if_dash(value: str | None) -> str | None:
    if value == "-":
        return sys.stdin.read()
    return value


def _build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="Emit the raw JSON result object from the tool.")
    common.add_argument("--strict", action="store_true", default=argparse.SUPPRESS,
                        help="Return exit code 1 when lint finds errors or compile fails.")

    parser = argparse.ArgumentParser(
        prog="pawnforge",
        description="Deterministic Pawn (SA-MP / open.mp) toolchain CLI.",
        parents=[common],
    )
    parser.set_defaults(json=False, strict=False)
    parser.add_argument("--version", action="version", version=f"pawn-forge {__version__}")

    sub = parser.add_subparsers(dest="command", required=True, metavar="<subcommand>")

    # 1. info -> project_info
    p_info = sub.add_parser("info", parents=[common], help="Inspect a Pawn project layout and platform.")
    p_info.add_argument("project_dir", nargs="?", default=".", help="Project directory (default: current directory).")

    # 2. compile -> compile
    p_comp = sub.add_parser("compile", parents=[common], help="Compile a .pwn file or inline snippet.")
    p_comp.add_argument("file", nargs="?", help="Path to the .pwn file.")
    p_comp.add_argument("--code", help="Inline source code (pass '-' to read from stdin).")
    p_comp.add_argument("--project-dir", help="Project root for include discovery.")
    p_comp.add_argument("--includes", nargs="+", action="extend", help="Extra include directories.")
    p_comp.add_argument("--define", dest="defines", action="append", metavar="NAME[=VAL]",
                        help="Preprocessor define (repeatable).")
    p_comp.add_argument("--flags", nargs="+", action="extend", help="Extra compiler flags.")
    p_comp.add_argument("--output", help="'temp' (default), 'alongside', or explicit .amx path.")
    p_comp.add_argument("--mode", choices=["auto", "pawncc", "sampctl"], help="Compiler backend mode.")
    p_comp.add_argument("--compat", action="store_true", default=None, help="Pass -Z for legacy SA-MP 0.3.7 includes.")
    p_comp.add_argument("--no-default-flags", dest="default_flags", action="store_false", default=None,
                        help="Do not add default -;+ and -(+ flags.")
    p_comp.add_argument("--normalize-includes", choices=["auto", "always", "never"],
                        help="Backslash #include path normalization mode.")
    p_comp.add_argument("--timeout", type=int, help="Compiler timeout in seconds.")

    # 3. install-compiler -> install_compiler
    p_inst = sub.add_parser("install-compiler", parents=[common],
                            help="Download the community open.mp Pawn compiler.")
    p_inst.add_argument("--version", help="Compiler version (e.g. 3.10.11).")

    # 4. lint -> lint
    p_lint = sub.add_parser("lint", parents=[common], help="Run Pawn static analysis.")
    p_lint.add_argument("path", nargs="?", help="File or directory to scan.")
    p_lint.add_argument("--code", help="Inline source code (pass '-' to read from stdin).")
    p_lint.add_argument("--rules", nargs="+", action="extend", help="Only run these rule IDs (e.g. PF101).")
    p_lint.add_argument("--exclude", nargs="+", action="extend", help="Rule IDs to skip.")
    p_lint.add_argument("--min-severity", choices=["info", "warning", "error"], help="Minimum severity to report.")
    p_lint.add_argument("--include-third-party", action="store_true", default=None,
                        help="Include third-party directories (dependencies/include/pawno/qawno).")
    p_lint.add_argument("--max-findings", type=int, help="Maximum findings returned.")

    # 5. lint-rules -> lint_rules
    sub.add_parser("lint-rules", parents=[common], help="List all Pawn Forge lint rules.")

    # 6. analyze-log -> analyze_log
    p_log = sub.add_parser("analyze-log", parents=[common], help="Analyze a SA-MP / open.mp server log.")
    p_log.add_argument("path", nargs="?", help="Log file or server directory.")
    p_log.add_argument("--text", help="Raw log text (pass '-' to read from stdin).")
    p_log.add_argument("--source-root", help="Source root directory for backtrace context.")
    p_log.add_argument("--tail-lines", type=int, help="Inspect only the last N lines.")
    p_log.add_argument("--max-incidents", type=int, help="Maximum grouped incidents to return.")

    # 7. lookup -> lookup
    p_lkp = sub.add_parser("lookup", parents=[common], help="Look up verified SA-MP / open.mp IDs.")
    p_lkp.add_argument("kind", choices=list(lookup.KINDS), help="Entity kind to look up.")
    p_lkp.add_argument("query", nargs="?", help="ID, name, or keyword.")
    p_lkp.add_argument("--library", help="Animation library (for kind=animation).")
    p_lkp.add_argument("--limit", type=int, help="Maximum results to return.")

    # 8. api -> api_lookup
    p_api = sub.add_parser("api", parents=[common], help="Look up native or callback signatures.")
    p_api.add_argument("--name", help="Exact native or callback name.")
    p_api.add_argument("--query", help="Search query across symbol names and summaries.")
    p_api.add_argument("--library", help="Filter by library name.")
    p_api.add_argument("--project-dir", help="Include project headers from this directory.")
    p_api.add_argument("--limit", type=int, help="Maximum results to return.")
    p_api.add_argument("--platform", choices=["auto", "open.mp", "sa-mp", "openmp", "samp"],
                       help="Target platform filter (auto, open.mp, sa-mp, openmp, samp).")

    # 9. migrate -> migrate_openmp
    p_mig = sub.add_parser("migrate", parents=[common], help="Plan or apply SA-MP -> open.mp migration.")
    p_mig.add_argument("file", nargs="?", help="Path to the .pwn file.")
    p_mig.add_argument("--code", help="Inline source code (pass '-' to read from stdin).")
    p_mig.add_argument("--write", choices=["none", "copy", "in_place", "return"],
                       help="Write mode (default: none).")

    # 10. textdraw -> convert_textdraws
    p_td = sub.add_parser("textdraw", parents=[common], help="Convert a TextDraw editor export to a clean module.")
    p_td.add_argument("file", nargs="?", help="Path to the TextDraw export file.")
    p_td.add_argument("--code", help="Inline export code (pass '-' to read from stdin).")
    p_td.add_argument("--prefix", help="Module identifier prefix (default: TD).")
    p_td.add_argument("--target", choices=["openmp", "samp"], help="Target API style.")
    p_td.add_argument("--ysi-hooks", action="store_true", default=None, help="Emit y_hooks lifecycle hooks.")
    p_td.add_argument("--write-to", help="Write generated module to a new file path.")

    # 11. run-server -> run_server
    p_srv = sub.add_parser("run-server", parents=[common], help="Run a local server headlessly (y_testing/smoke).")
    p_srv.add_argument("server_dir", help="Server directory containing omp-server or samp-server.")
    p_srv.add_argument("--script", help="Gamemode name in gamemodes/ (without .amx).")
    p_srv.add_argument("--amx-path", "--amx", dest="amx_path", help="Path to compiled .amx to run.")
    p_srv.add_argument("--timeout", dest="timeout_s", type=int, help="Timeout in seconds.")
    p_srv.add_argument("--stop-on", help="Regex pattern that stops the server when matched.")
    p_srv.add_argument("--config", action="append", metavar="KEY=VAL",
                       help="Extra open.mp config override (repeatable).")

    return parser


def _drop_none(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


def _dispatch(ns: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    cmd = ns.command
    if cmd == "info":
        return "project_info", {"project_dir": ns.project_dir}
    if cmd == "compile":
        args = _drop_none({
            "file": ns.file,
            "code": _read_stdin_if_dash(ns.code),
            "project_dir": ns.project_dir,
            "includes": ns.includes,
            "defines": _parse_kv_pairs(ns.defines),
            "flags": ns.flags,
            "output": ns.output,
            "mode": ns.mode,
            "compat": True if ns.compat else None,
            "default_flags": ns.default_flags,
            "normalize_includes": ns.normalize_includes,
            "timeout": ns.timeout,
        })
        return "compile", args
    if cmd == "install-compiler":
        return "install_compiler", _drop_none({"version": ns.version})
    if cmd == "lint":
        args = _drop_none({
            "path": ns.path,
            "code": _read_stdin_if_dash(ns.code),
            "rules": ns.rules,
            "exclude": ns.exclude,
            "min_severity": ns.min_severity,
            "include_third_party": True if ns.include_third_party else None,
            "max_findings": ns.max_findings,
        })
        return "lint", args
    if cmd == "lint-rules":
        return "lint_rules", {}
    if cmd == "analyze-log":
        args = _drop_none({
            "path": ns.path,
            "text": _read_stdin_if_dash(ns.text),
            "source_root": ns.source_root,
            "tail_lines": ns.tail_lines,
            "max_incidents": ns.max_incidents,
        })
        return "analyze_log", args
    if cmd == "lookup":
        args = _drop_none({
            "kind": ns.kind,
            "query": ns.query,
            "library": ns.library,
            "limit": ns.limit,
        })
        return "lookup", args
    if cmd == "api":
        args = _drop_none({
            "name": ns.name,
            "query": ns.query,
            "library": ns.library,
            "project_dir": ns.project_dir,
            "limit": ns.limit,
            "platform": ns.platform,
        })
        return "api_lookup", args
    if cmd == "migrate":
        args = _drop_none({
            "file": ns.file,
            "code": _read_stdin_if_dash(ns.code),
            "write": ns.write,
        })
        return "migrate_openmp", args
    if cmd == "textdraw":
        args = _drop_none({
            "file": ns.file,
            "code": _read_stdin_if_dash(ns.code),
            "prefix": ns.prefix,
            "target": ns.target,
            "ysi_hooks": True if ns.ysi_hooks else None,
            "write_to": ns.write_to,
        })
        return "convert_textdraws", args
    if cmd == "run-server":
        args = _drop_none({
            "server_dir": ns.server_dir,
            "script": ns.script,
            "amx_path": ns.amx_path,
            "timeout_s": ns.timeout_s,
            "stop_on": ns.stop_on,
            "config": _parse_kv_pairs(ns.config, coerce=True),
        })
        return "run_server", args
    raise ValueError(f"Unknown subcommand: {cmd}")


def _format_text(cmd: str, res: dict[str, Any]) -> str:
    if res.get("ok") is False or (res.get("error") and "ok" not in res):
        lines = [f"Error: {res.get('error', 'Command failed.')}"]
        if res.get("how_to_fix"):
            lines.append(f"How to fix: {res['how_to_fix']}")
        return "\n".join(lines)

    if cmd == "info":
        libs = ", ".join(sorted(res.get("libraries_detected", {}))) or "none"
        comp = res.get("compiler") or {}
        comp_str = f"{comp.get('kind', 'found')} ({comp.get('path', '')})" if comp.get("found") else "not found"
        lines = [
            f"Root: {res.get('root')}",
            f"Platform: {res.get('platform')}",
            f"Main script: {res.get('main_script') or 'none'}",
            f"Libraries: {libs}",
            f"Compiler: {comp_str}",
        ]
        if res.get("include_dirs"):
            lines.append(f"Include dirs: {', '.join(res['include_dirs'])}")
        return "\n".join(lines)

    if cmd == "compile":
        lines = [f"Compile {'OK' if res.get('ok') else 'FAILED'} "
                 f"(errors: {res.get('errors', 0)}, warnings: {res.get('warnings', 0)})"]
        for d in res.get("diagnostics", []):
            lines.append(f"  {d.get('file')}:{d.get('line')} [{d.get('severity')} {d.get('code')}] {d.get('message')}")
        if res.get("amx"):
            lines.append(f"AMX: {res['amx']}")
        if res.get("next_step"):
            lines.append(f"Next: {res['next_step']}")
        return "\n".join(lines)

    if cmd == "install-compiler":
        lines = [f"Installed compiler {res.get('version', '')}: {res.get('path', '')}"]
        if res.get("note"):
            lines.append(res["note"])
        return "\n".join(lines)

    if cmd == "lint":
        s = res.get("summary", {})
        lines = [f"Scanned {res.get('files_scanned', 0)} file(s): "
                 f"{s.get('error', 0)} error(s), {s.get('warning', 0)} warning(s), {s.get('info', 0)} info"]
        for f in res.get("findings", []):
            lines.append(f"  {f.get('file')}:{f.get('line')} [{f.get('severity')} {f.get('rule')}] {f.get('message')}")
        return "\n".join(lines)

    if cmd == "lint-rules":
        return "\n".join(
            f"{r['id']} [{r['severity']}] ({r['category']}): {r['title']}"
            for r in res.get("rules", [])
        )

    if cmd == "analyze-log":
        lines = [f"Scanned {res.get('lines_scanned', 0)} lines; {res.get('incident_groups', 0)} incident group(s)."]
        for g in res.get("incidents", []):
            lines.append(f"  {g.get('count', 1)}x {g.get('type')} {g.get('code', '')}: {g.get('title') or g.get('message')}")
            if g.get("hint"):
                lines.append(f"     Hint: {g['hint']}")
        if res.get("missing_natives"):
            lines.append(f"Missing natives: {', '.join(res['missing_natives'])}")
        if res.get("plugin_failures"):
            lines.append(f"Plugin failures: {len(res['plugin_failures'])}")
        return "\n".join(lines)

    if cmd == "lookup":
        lines: list[str] = []
        if "valid" in res:
            lines.append(f"Valid: {res['valid']}")
        if res.get("message"):
            lines.append(res["message"])
        for it in res.get("results", []):
            if isinstance(it, list):
                lines.append("  " + " | ".join(map(str, it)))
            elif isinstance(it, dict):
                ident = it.get("id", it.get("interior", ""))
                name = it.get("name", it.get("model_name", ""))
                lib = f" [{it['library']}]" if it.get("library") else ""
                lines.append(f"  {ident}: {name}{lib}".strip())
        if res.get("usage"):
            lines.append(f"Usage: {res['usage']}")
        if res.get("libraries"):
            lines.append(f"Libraries: {', '.join(res['libraries'])}")
        if res.get("sections"):
            lines.append(f"Sections: {', '.join(res['sections'])}")
        if res.get("note"):
            lines.append(res["note"])
        return "\n".join(lines) if lines else json.dumps(res, ensure_ascii=False, indent=2, default=str)

    if cmd == "api":
        if res.get("found") is False:
            lines = [res.get("message", "Not found.")]
            if res.get("did_you_mean"):
                lines.append(f"Did you mean: {', '.join(res['did_you_mean'])}")
            return "\n".join(lines)
        if "results" in res:
            lines = []
            for r in res["results"]:
                lines.append(f"[{r.get('library')}] {r.get('signature')}")
                if r.get("summary"):
                    lines.append(f"  {r['summary']}")
            if res.get("openmp_deprecation"):
                lines.append(f"open.mp deprecation: {res['openmp_deprecation']}")
            return "\n".join(lines) if lines else "No matching declarations."
        if "libraries" in res:
            return "\n".join(f"  {k}: {v}" for k, v in sorted(res["libraries"].items()))

    if cmd == "migrate":
        lines = [f"Safe changes: {res.get('safe_changes', 0)}, Manual items: {res.get('manual_changes', 0)}"]
        if res.get("written"):
            lines.append(f"Written: {res['written']}")
        if res.get("backup"):
            lines.append(f"Backup: {res['backup']}")
        if res.get("diff"):
            lines.append(res["diff"].rstrip())
        return "\n".join(lines)

    if cmd == "textdraw":
        lines = [f"TextDraws: {res.get('globals', 0)} global, {res.get('player', 0)} player"]
        for w in res.get("warnings", []):
            lines.append(f"  Warning: {w}")
        if res.get("written"):
            lines.append(f"Written: {res['written']}")
        elif res.get("code"):
            lines.append(res["code"].rstrip())
        return "\n".join(lines)

    if cmd == "run-server":
        lines = [f"Server: {res.get('server')} (port {res.get('port')}), "
                 f"stop_reason={res.get('stop_reason')}, passed={res.get('passed')}"]
        if res.get("y_testing"):
            yt = res["y_testing"]
            lines.append(f"y_testing: {yt.get('tests')} tests, {yt.get('checks')} checks, {yt.get('fails')} fails")
        if res.get("script_errors"):
            lines.append("Script errors: " + "; ".join(res["script_errors"]))
        return "\n".join(lines)

    return json.dumps(res, ensure_ascii=False, indent=2, default=str)


def _exit_code(cmd: str, res: dict[str, Any], strict: bool) -> int:
    if res.get("ok") is False:
        return 1
    if "error" in res and "ok" not in res:
        return 1
    if strict and cmd == "lint" and res.get("summary", {}).get("error", 0) > 0:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = _build_parser()
    ns = parser.parse_args(argv)
    try:
        tool_name, tool_args = _dispatch(ns)
        res = call_tool(tool_name, tool_args)
    except (KeyError, ValueError, TypeError, OSError) as exc:
        res = {"ok": False, "error": str(exc)}

    if ns.json:
        print(json.dumps(res, ensure_ascii=False, indent=2, default=str))
    else:
        print(_format_text(ns.command, res))
    return _exit_code(ns.command, res, bool(ns.strict))
