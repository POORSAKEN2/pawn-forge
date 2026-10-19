"""Parse SA-MP / open.mp server logs: CrashDetect runtime errors, crashes,
long callbacks, missing natives and plugin load failures.

Repeated incidents are grouped by signature so a log with ten thousand
copies of the same out-of-bounds error reports one root cause with a count.
"""
from __future__ import annotations

import re
from pathlib import Path

PREFIX_RE = re.compile(r"^(?:\s*\[[^\]]{1,40}\]\s*)+")
RUNTIME_RE = re.compile(r'Run time error (\d+):\s*"([^"]*)"')
FRAME_RE = re.compile(
    r"^#(?P<idx>\d+)\s+(?:(?P<addr>[0-9a-fA-F]{6,16})\s+)?in\s+"
    r"(?:(?P<kind>public|stock|native)\s+)?(?P<func>[^\s(]+|\?\?)\s*\((?P<args>.*?)\)"
    r"(?:\s+at\s+(?P<file>.+?):(?P<line>\d+)|\s+(?:from|in)\s+(?P<module>\S+))?\s*$"
)
NATIVE_FRAME_RE = re.compile(r"^#(?P<idx>\d+)\s+native\s+(?P<func>\w+)\s*\((?P<args>.*?)\)\s+(?:from|in)\s+(?P<module>\S+)")
MISSING_NATIVE_RE = re.compile(r"(?i)(?:function|native(?: function)?)\s+(?:is\s+)?not\s+(?:registered|found)\s*[:\s]\s*'?\"?(\w+)")
PLUGIN_FAIL_RE = re.compile(r"(?i)(failed\s*\(([^)]*)\)|failed to load (?:plugin|component)[^:]*:?\s*(.*)|"
                            r"plugin .* (?:failed|could not be loaded|not found)(.*))")

AMX_ERRORS = {
    1: ("Forced exit", "The script called exit or a native requested termination."),
    2: ("Assertion failed", "An assert() expression was false. Check the asserted condition at the top frame."),
    3: ("Stack/heap collision", "The script ran out of stack/heap: very large local arrays, deep or unbounded recursion, "
                                 "or large strings passed by value. Shrink locals, make big buffers static/global, or raise "
                                 "#pragma dynamic."),
    4: ("Array index out of bounds", "An index was outside the array. Validate indices before use: player/vehicle IDs that "
                                     "can be INVALID_PLAYER_ID (65535) or INVALID_VEHICLE_ID, -1 from strfind/sscanf failures, "
                                     "dialog listitem values, and loop bounds using <= instead of <."),
    5: ("Invalid memory access", "The script read/wrote outside its memory, often via a bad reference, a corrupted array "
                                 "index computed from player input, or an include/plugin version mismatch."),
    6: ("Invalid instruction", "The .amx is corrupted or incompatible with the server/JIT. Recompile with the matching "
                               "compiler and includes."),
    7: ("Stack underflow", "Stack corruption, usually from mismatched native declarations (include vs plugin version)."),
    8: ("Heap underflow", "Heap corruption, usually from mismatched native declarations or a misbehaving plugin."),
    10: ("Native function failed", "A native reported failure. Check the arguments at the frame that called it."),
    11: ("Divide by zero", "A division or modulo by zero. Guard the divisor."),
    19: ("File or function is not found", "A native used by the script is not provided by any loaded plugin/component. "
                                          "Load the plugin (config.json legacy_plugins / server.cfg plugins) or match the "
                                          "include version to the plugin version."),
    20: ("Invalid index parameter", "A public function index is invalid; the callback may be misspelled or not public."),
    27: ("General error", "Unspecified AMX error; inspect the backtrace."),
}


def _clean(line: str) -> str:
    s = PREFIX_RE.sub("", line.rstrip("\r\n"))
    # CrashDetect lines usually carry "[debug]" after the timestamp; open.mp adds "[Info]".
    s = re.sub(r"^\s*(?:\[debug\]\s*)", "", s)
    return s.rstrip()


def _frame(text: str) -> dict | None:
    t = text.strip()
    m = FRAME_RE.match(t)
    if m:
        f = {"index": int(m.group("idx")), "function": m.group("func")}
        if m.group("kind"):
            f["kind"] = m.group("kind")
        if m.group("args"):
            f["args"] = m.group("args")[:200]
        if m.group("file"):
            f["file"] = m.group("file")
            f["line"] = int(m.group("line"))
        if m.group("module"):
            f["module"] = m.group("module")
        return f
    m = NATIVE_FRAME_RE.match(t)
    if m:
        return {"index": int(m.group("idx")), "kind": "native", "function": m.group("func"),
                "module": m.group("module")}
    if re.match(r"^#\d+\s", t):
        return {"index": int(t[1:].split()[0]), "raw": t[:240]}
    return None


def _source_context(frames: list[dict], source_root: Path | None) -> None:
    if not source_root:
        return
    index: dict[str, list[Path]] | None = None
    for f in frames:
        if "file" not in f:
            continue
        cand = Path(f["file"])
        path = cand if cand.is_file() else None
        if path is None:
            if index is None:
                index = {}
                for p in source_root.rglob("*"):
                    if p.suffix.lower() in (".pwn", ".inc", ".p"):
                        index.setdefault(p.name.lower(), []).append(p)
            name = re.split(r"[\\/]", f["file"])[-1].lower()
            hits = index.get(name, [])
            path = hits[0] if len(hits) == 1 else None
        if path is None:
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        ln = f["line"]
        lo, hi = max(1, ln - 3), min(len(lines), ln + 3)
        f["resolved_file"] = str(path)
        f["context"] = [f"{'>' if i == ln else ' '}{i:5d} | {lines[i - 1]}" for i in range(lo, hi + 1)]


def analyze_log(path: str | None = None, text: str | None = None, source_root: str | None = None,
                tail_lines: int = 50000, max_incidents: int = 25) -> dict:
    if text is None:
        if not path:
            return {"ok": False, "error": "Pass path or text."}
        p = Path(path).expanduser()
        if p.is_dir():
            for name in ("log.txt", "server_log.txt", "logs/log.txt"):
                if (p / name).is_file():
                    p = p / name
                    break
        if not p.is_file():
            return {"ok": False, "error": f"Log not found: {p}"}
        text = p.read_text(encoding="utf-8", errors="replace")
    raw_lines = text.splitlines()
    total_lines = len(raw_lines)
    raw_lines = raw_lines[-tail_lines:]
    lines = [_clean(l) for l in raw_lines]

    incidents: list[dict] = []
    missing_natives: set[str] = set()
    plugin_failures: list[str] = []
    other_errors: dict[str, int] = {}
    i, n = 0, len(lines)

    def read_backtraces(j: int, inc: dict) -> int:
        while j < n:
            s = lines[j].strip()
            if s in ("AMX backtrace:", "Native backtrace:"):
                key = "amx_backtrace" if s.startswith("AMX") else "native_backtrace"
                inc[key] = []
                j += 1
                while j < n:
                    fr = _frame(lines[j])
                    if fr is None:
                        break
                    inc[key].append(fr)
                    j += 1
                continue
            if inc.get("code") == 19 and re.fullmatch(r"[A-Za-z_@][\w@]*", s):
                # CrashDetect lists each unresolved native on its own line after error 19.
                inc.setdefault("missing_natives", []).append(s)
                j += 1
                continue
            if s.startswith(("Attempted to", "Accessing element", "Index", "Native backtrace", "Loaded modules",
                             "Registers:", "Stack:", "Exception code")) or re.match(r"^\s{1,}\S", lines[j]):
                inc.setdefault("details", []).append(s[:300])
                j += 1
                if s.startswith(("Loaded modules", "Registers:", "Stack:")):
                    # Skip the dump block that follows.
                    while j < n and (re.match(r"^\s*[0-9a-fA-F]{8}", lines[j].strip()) or lines[j].startswith(" ")):
                        j += 1
                continue
            break
        return j

    while i < n:
        s = lines[i].strip()
        m = RUNTIME_RE.search(s)
        if m:
            code = int(m.group(1))
            inc = {"type": "runtime_error", "code": code, "message": m.group(2), "log_line": total_lines - len(lines) + i + 1}
            i = read_backtraces(i + 1, inc)
            for d in inc.get("details", []):
                mm = MISSING_NATIVE_RE.search(d)
                if mm:
                    missing_natives.add(mm.group(1))
            missing_natives.update(inc.get("missing_natives", []))
            incidents.append(inc)
            continue
        if s.startswith("Server crashed"):
            inc = {"type": "crash", "message": s, "log_line": total_lines - len(lines) + i + 1}
            i = read_backtraces(i + 1, inc)
            incidents.append(inc)
            continue
        if s.startswith("Long callback execution detected"):
            inc = {"type": "long_callback", "message": s, "log_line": total_lines - len(lines) + i + 1}
            i = read_backtraces(i + 1, inc)
            incidents.append(inc)
            continue
        mm = MISSING_NATIVE_RE.search(s)
        if mm:
            missing_natives.add(mm.group(1))
        elif PLUGIN_FAIL_RE.search(s) and re.search(r"(?i)plugin|\.so|\.dll|component", s):
            plugin_failures.append(s[:300])
        elif re.search(r"(?i)\b(error|failed)\b", s) and not s.startswith("#"):
            key = re.sub(r"\d+", "N", s)[:160]
            other_errors[key] = other_errors.get(key, 0) + 1
        i += 1

    # Group by signature.
    groups: dict[tuple, dict] = {}
    for inc in incidents:
        top = next((f for f in inc.get("amx_backtrace", []) if f.get("function") not in (None, "??")), None)
        sig = (inc["type"], inc.get("code"), top.get("function") if top else None,
               top.get("file") if top else None, top.get("line") if top else None,
               tuple(d for d in inc.get("details", []) if d.startswith(("Attempted", "Accessing")))[:1])
        g = groups.get(sig)
        if g:
            g["count"] += 1
            g["last_log_line"] = inc["log_line"]
        else:
            inc["count"] = 1
            inc["first_log_line"] = inc.pop("log_line")
            inc["last_log_line"] = inc["first_log_line"]
            groups[sig] = inc
    root = Path(source_root).expanduser() if source_root else None
    out = sorted(groups.values(), key=lambda g: -g["count"])[:max_incidents]
    for g in out:
        if g["type"] == "runtime_error":
            title, hint = AMX_ERRORS.get(g["code"], (g["message"], "Inspect the top AMX frame."))
            g["title"] = title
            g["hint"] = hint
            for d in g.get("details", []):
                mm = re.search(r"index (-?\d+)\D+(?:size|bound) (\d+)", d)
                if mm:
                    idx, size = int(mm.group(1)), int(mm.group(2))
                    if "upper bound" in d:
                        size += 1
                    g["index"], g["array_size"] = idx, size
                    if idx == 65535:
                        g["hint"] += " Index 65535 is INVALID_PLAYER_ID / INVALID_VEHICLE_ID: an invalid ID reached an array lookup."
                    elif idx < 0:
                        g["hint"] += " A negative index usually comes from a failed lookup (-1) used without checking."
                    elif idx == size:
                        g["hint"] += " The index equals the size: an off-by-one (<= instead of <) or a missing bound check."
        elif g["type"] == "long_callback":
            g["hint"] = ("A callback ran longer than CrashDetect's long-call threshold: look for unbounded loops, blocking "
                         "mysql_query/file I/O, or large loops in the top frame.")
        elif g["type"] == "crash":
            mods = [f.get("module") for f in g.get("native_backtrace", []) if f.get("module")]
            suspects = [m for m in mods if not re.search(r"crashdetect|libc|libstdc|samp03svr|samp-server|omp-server|kernel|ntdll", m, re.I)]
            if suspects:
                g["suspect_module"] = suspects[0]
            g["hint"] = ("The server process crashed (not a script runtime error). The AMX backtrace shows the script "
                         "call that was running; the native backtrace points at the module that faulted"
                         + (f" (most likely {suspects[0]})" if suspects else "") + ". Check plugin versions and the arguments "
                         "passed to that plugin's natives.")
        frames = g.get("amx_backtrace", [])
        if frames and not any("file" in f for f in frames):
            g["note"] = ("No source file/line in the backtrace: compile with -d3 and load crashdetect to get "
                         "file:line frames.")
        _source_context(g.get("amx_backtrace", []), root)

    return {
        "ok": True,
        "lines_scanned": len(lines),
        "incident_groups": len(groups),
        "incidents": out,
        "missing_natives": sorted(missing_natives),
        "plugin_failures": plugin_failures[:30],
        "other_errors": [{"pattern": k, "count": v} for k, v in sorted(other_errors.items(), key=lambda kv: -kv[1])[:20]],
        "crashdetect_present": bool(incidents) or "crashdetect" in text.lower(),
    }
