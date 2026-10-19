"""Compiler bridge: locate pawncc / sampctl, compile, and parse diagnostics."""
from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

from .project import find_root, include_dirs

DIAG_RE = re.compile(
    r"^(?P<file>.+?)\((?P<line>\d+)(?:\s*--\s*(?P<end>\d+))?\)\s*:\s*"
    r"(?P<sev>fatal error|user error|user warning|error|warning)(?:\s+(?P<code>\d+))?:\s*(?P<msg>.*)$"
)
INCLUDE_DIRECTIVE = re.compile(r'^([ \t]*#[ \t]*(?:try)?include[ \t]*[<"])([^>"\n]+)([>"])', re.M)
DEFAULT_FLAGS = ["-;+", "-(+"]  # require semicolons and call parentheses (YSI expects -;+)
VERSION_RE = re.compile(r"Pawn compiler\s+(\d+\.\d+(?:\.\d+)*)")
STACK_RE = re.compile(r"Stack/heap size:\s*(\d+) bytes; estimated max\. usage[=:]\s*(.*)$", re.M)

# Fix hints for the diagnostics people hit most. Message texts are the compiler's;
# hints are guidance for the fix, never a suggestion to silence the diagnostic.
HINTS = {
    "001": "A token is missing. Check the line above too: a missing ';', ')' or '}' is often reported one line late.",
    "004": "The function is declared (forward/native) but never implemented, or its name is misspelled.",
    "010": "Invalid function or declaration. Usually a stray token, a missing brace, or code outside a function.",
    "012": "Calling something that is not a function. Check for a variable shadowing the function name.",
    "017": "Undefined symbol: the include that declares it is missing, the name is misspelled, or it is declared after use inside a different scope. Use the api_lookup tool to find which include declares it.",
    "020": "Invalid symbol name. Names cannot start with a digit or contain special characters.",
    "021": "Symbol already defined. Two declarations share a name (often a global and a local, or two includes).",
    "022": "Must be an lvalue: you are assigning to something that is not a variable (e.g. a function call or a constant).",
    "025": "Function heading differs from its prototype. With open.mp includes, callbacks use tagged parameters (e.g. OnPlayerDeath(playerid, killerid, WEAPON:reason)). Copy the forward from the include.",
    "028": "Invalid subscript: indexing something that is not an array, or using too many dimensions.",
    "029": "Invalid expression. Commonly a missing operator, a macro that expanded badly, or a stray character.",
    "030": "Compound statement not closed at end of file: a '{' is missing its '}'.",
    "032": "Constant array index out of bounds. Arrays of size N are indexed 0..N-1.",
    "033": "Array must be indexed: you used an array where a single cell is expected.",
    "035": "Argument type mismatch: passing a single value where an array/string is expected, or vice versa.",
    "036": "Empty statement: a stray ';' after if/for/while.",
    "047": "Array sizes do not match, or the destination is too small. Use strcopy/format with sizeof() instead of '=' for strings.",
    "048": "Array dimensions do not match.",
    "054": "Unmatched closing brace.",
    "075": "Input line too long. Split the line or the string literal.",
    "100": "Cannot read from file: the include is not on the include path. Pass include paths or install the dependency (sampctl ensure).",
    "202": "Number of arguments does not match the definition. Check the exact signature with api_lookup.",
    "203": "Symbol is never used. Remove it, or if it is a public callback, make sure it is spelled correctly.",
    "204": "Value assigned but never used. Remove the dead assignment or use the value.",
    "208": "Function with tag result used before definition. Add a forward declaration with the tag.",
    "209": "Function should return a value on every path. Add a return at the end.",
    "211": "Possibly unintended assignment: '=' inside a condition. Use '==' for comparison.",
    "213": "Tag mismatch. With open.mp includes use the proper tagged constants (true/false for bool:, WEAPON_*, TEXT_DRAW_FONT_*, Float: for floats). Do not cast tags away to hide this.",
    "214": "Possibly a 'const' array argument was intended: mark read-only array parameters as const.",
    "215": "Expression has no effect: a statement that computes something and discards it (often '==' used instead of '=').",
    "217": "Loose indentation. Usually harmless, but fix it: it often hides a missing brace.",
    "219": "Local variable shadows a variable at a preceding level. Rename one of them.",
    "225": "Unreachable code after return/break/continue.",
    "234": "Deprecated function. Use the replacement named in the message (migrate_openmp can rewrite safe renames).",
    "235": "Public function lacks a forward declaration. Add 'forward Name(params);'.",
    "239": "Literal string passed to a non-const parameter. Mark the parameter 'const' in your function.",
    "240": "Assigned value is never used before being overwritten.",
}


# --------------------------------------------------------------------------- discovery
def _plugin_data_dir() -> Path:
    d = os.environ.get("CLAUDE_PLUGIN_DATA") or os.environ.get("PAWNFORGE_DATA_DIR")
    if d:
        return Path(d)
    return Path(tempfile.gettempdir()) / "pawn-forge"


def _exe(name: str) -> str:
    return name + (".exe" if os.name == "nt" else "")


def _env_for(pawncc: Path) -> dict:
    env = dict(os.environ)
    lib = pawncc.parent.parent / "lib"
    if lib.is_dir():
        key = "DYLD_LIBRARY_PATH" if sys.platform == "darwin" else "LD_LIBRARY_PATH"
        env[key] = os.pathsep.join(filter(None, [str(lib), env.get(key, "")]))
    return env


def _version(pawncc: Path) -> tuple[str | None, str | None]:
    try:
        r = subprocess.run([str(pawncc)], capture_output=True, text=True, timeout=15, env=_env_for(pawncc))
        out = (r.stdout or "") + (r.stderr or "")
        m = VERSION_RE.search(out)
        if m:
            return m.group(1), None
        return None, out.strip()[:400] or f"exit code {r.returncode}"
    except OSError as exc:
        hint = ""
        if sys.platform.startswith("linux"):
            hint = (" The Linux pawncc build is 32-bit: install the i386 C runtime "
                    "(Debian/Ubuntu: sudo apt install libc6-i386; Fedora: sudo dnf install glibc.i686).")
        return None, f"{exc}.{hint}"
    except subprocess.TimeoutExpired:
        return None, "timed out while querying version"


def find_compiler(project_dir: str | None = None) -> dict:
    searched: list[str] = []
    cands: list[tuple[Path, str]] = []
    for var in ("PAWNFORGE_PAWNCC", "PAWNCC"):
        v = os.environ.get(var, "").strip()
        if v:
            cands.append((Path(v), f"${var}"))
    if project_dir:
        root = find_root(project_dir)
        for rel in ("qawno", "pawno", ".pawncc/bin", "tools/pawncc/bin", "compiler/bin", "."):
            cands.append((root / rel / _exe("pawncc"), f"project:{rel}"))
    installed = _plugin_data_dir() / "compiler"
    if installed.is_dir():
        for p in sorted(installed.glob(f"*/bin/{_exe('pawncc')}"), reverse=True):
            cands.append((p, "pawn-forge install_compiler"))
    w = shutil.which("pawncc")
    if w:
        cands.append((Path(w), "PATH"))

    for path, origin in cands:
        searched.append(f"{origin}: {path}")
        if path.is_file():
            ver, err = _version(path)
            if ver:
                return {"found": True, "kind": "pawncc", "path": str(path), "version": ver, "origin": origin}
            return {"found": False, "path": str(path), "origin": origin,
                    "error": f"pawncc exists but did not run: {err}"}
    sampctl = shutil.which("sampctl")
    if sampctl:
        return {"found": True, "kind": "sampctl", "path": sampctl, "origin": "PATH",
                "note": "No standalone pawncc found; sampctl manages its own compiler."}
    return {
        "found": False,
        "searched": searched,
        "how_to_fix": "Call the install_compiler tool to download the community compiler, set the plugin's "
                      "pawncc_path option, add pawncc to PATH, or place it in qawno/ in the project.",
    }


# --------------------------------------------------------------------------- install
def install_compiler(version: str = "3.10.11") -> dict:
    sysname = platform.system().lower()
    if sysname.startswith("win"):
        url = f"https://github.com/openmultiplayer/compiler/releases/download/v{version}/pawnc-{version}-windows.zip"
    elif sysname == "linux":
        url = f"https://github.com/openmultiplayer/compiler/releases/download/v{version}/pawnc-{version}-linux.tar.gz"
    elif sysname == "darwin":
        version = "3.10.10"  # last release with a macOS build
        url = f"https://github.com/pawn-lang/compiler/releases/download/v{version}/pawnc-{version}-macos.zip"
    else:
        return {"ok": False, "error": f"No prebuilt compiler for {platform.system()}."}
    dest = _plugin_data_dir() / "compiler"
    dest.mkdir(parents=True, exist_ok=True)
    archive = dest / url.rsplit("/", 1)[1]
    try:
        with urllib.request.urlopen(url, timeout=60) as r, open(archive, "wb") as fh:  # noqa: S310 - fixed https URL
            shutil.copyfileobj(r, fh)
    except Exception as exc:
        return {"ok": False, "url": url, "error": f"download failed: {exc}"}
    try:
        if archive.suffix == ".zip":
            with zipfile.ZipFile(archive) as z:
                for m in z.namelist():
                    if m.startswith("/") or ".." in Path(m).parts:
                        return {"ok": False, "error": f"refusing unsafe archive path {m}"}
                z.extractall(dest)
        else:
            with tarfile.open(archive) as t:
                for m in t.getmembers():
                    if m.name.startswith("/") or ".." in Path(m.name).parts or m.issym() or m.islnk():
                        return {"ok": False, "error": f"refusing unsafe archive entry {m.name}"}
                t.extractall(dest)  # noqa: S202 - members validated above
    finally:
        archive.unlink(missing_ok=True)
    exes = sorted(dest.glob(f"*{version}*/**/{_exe('pawncc')}"))
    if not exes:
        return {"ok": False, "error": "archive did not contain pawncc"}
    exe = exes[0]
    if os.name != "nt":
        exe.chmod(0o755)
        for f in exe.parent.iterdir():
            f.chmod(0o755)
    ver, err = _version(exe)
    res = {"ok": ver is not None, "path": str(exe), "version": ver or version, "source": url}
    if err:
        res["warning"] = err
    if sysname == "darwin":
        res["note"] = "macOS build is x86_64; on Apple Silicon it runs under Rosetta 2."
    return res


# --------------------------------------------------------------------------- compile
def _sampctl_build(root: Path, timeout: int) -> tuple[int, str, list[str]]:
    sampctl = shutil.which("sampctl")
    help_out = subprocess.run([sampctl, "--help"], capture_output=True, text=True, timeout=30)
    uses_package = re.search(r"^\s*package\b", (help_out.stdout or "") + (help_out.stderr or ""), re.M)
    cmd = [sampctl, "package", "build"] if uses_package else [sampctl, "build"]
    r = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout or "") + (r.stderr or ""), cmd


def parse_output(output: str, cwd: Path, main_file: Path | None = None, inc_dirs: list[Path] | None = None) -> dict:
    diags = []
    for raw in output.splitlines():
        m = DIAG_RE.match(raw.strip())
        if not m:
            continue
        f = Path(m.group("file"))
        if not f.is_absolute():
            f = cwd / f
        f = Path(os.path.normpath(f))
        raw_sev = m.group("sev")
        sev = {"fatal error": "fatal", "user error": "error", "user warning": "warning"}.get(raw_sev, raw_sev)
        code = m.group("code").zfill(3) if m.group("code") else "user"
        d = {
            "file": str(f),
            "line": int(m.group("line")),
            "severity": sev,
            "code": code,
            "message": m.group("msg").strip(),
        }
        if m.group("end"):
            d["end_line"] = int(m.group("end"))
        if main_file is not None:
            d["in_include"] = f.resolve() != main_file.resolve() and any(
                str(f).startswith(str(i)) for i in (inc_dirs or []))
        if code in HINTS:
            d["hint"] = HINTS[code]
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
            ln = d["line"]
            if 0 < ln <= len(lines):
                d["source"] = lines[ln - 1].strip()[:240]
        except OSError:
            pass
        diags.append(d)
    stack = None
    sm = STACK_RE.search(output)
    if sm:
        stack = {"stack_heap_bytes": int(sm.group(1)), "estimated_max_usage": sm.group(2).strip()}
        if "recursion" in sm.group(2):
            stack["warning"] = "Recursion detected: stack usage cannot be bounded at compile time."
        else:
            um = re.search(r"(\d+) cells \((\d+) bytes\)", sm.group(2))
            if um and int(um.group(2)) > 0.75 * int(sm.group(1)):
                stack["warning"] = ("Estimated stack usage is over 75% of the stack/heap size. Reduce large local "
                                    "arrays or raise it with #pragma dynamic.")
    return {"diagnostics": diags, "stack": stack}


def _has_backslash_includes(dirs: list[Path], limit: int = 4000) -> bool:
    seen = 0
    for d in dirs:
        for root, dns, fns in os.walk(d, followlinks=True):
            dns[:] = [x for x in dns if x != ".git"]
            for fn in fns:
                if not fn.lower().endswith((".inc", ".pwn", ".p")):
                    continue
                seen += 1
                if seen > limit:
                    return False
                try:
                    with open(os.path.join(root, fn), encoding="utf-8", errors="replace") as fh:
                        for m in INCLUDE_DIRECTIVE.finditer(fh.read()):
                            if "\\" in m.group(2):
                                return True
                except OSError:
                    continue
    return False


def _mirror_tree(src: Path) -> Path:
    """Mirror .pwn/.inc files of `src` with `\\` -> `/` in #include directives only.

    The Linux/macOS compilers treat backslashes in include paths literally, which
    breaks YSI and most Windows-authored code. Line numbers are unchanged, so
    diagnostics map 1:1 back to the original files. Cached by mtime.
    """
    import hashlib

    dst = _plugin_data_dir() / "include-mirror" / hashlib.sha1(str(src).encode()).hexdigest()[:16]
    visited: set[str] = set()
    for root, dns, fns in os.walk(src, followlinks=True):
        real = os.path.realpath(root)
        if real in visited:
            dns[:] = []
            continue
        visited.add(real)
        dns[:] = [x for x in dns if x != ".git"]
        rel_root = os.path.relpath(root, src)
        for fn in fns:
            if not fn.lower().endswith((".inc", ".pwn", ".p")):
                continue
            s = os.path.join(root, fn)
            d = dst / rel_root / fn
            try:
                st = os.stat(s)
                if d.exists() and d.stat().st_mtime == st.st_mtime:
                    continue
                d.parent.mkdir(parents=True, exist_ok=True)
                with open(s, encoding="utf-8", errors="surrogateescape") as fh:
                    text = fh.read()
                text = INCLUDE_DIRECTIVE.sub(lambda m: m.group(1) + m.group(2).replace("\\", "/") + m.group(3), text)
                with open(d, "w", encoding="utf-8", errors="surrogateescape", newline="") as fh:
                    fh.write(text)
                os.utime(d, (st.st_atime, st.st_mtime))
            except OSError:
                continue
    return dst


def compile_pawn(file: str | None = None, code: str | None = None, project_dir: str | None = None,
                 includes: list[str] | None = None, defines: dict | None = None, flags: list[str] | None = None,
                 output: str = "temp", mode: str = "auto", compat: bool = False, timeout: int = 180,
                 max_diagnostics: int = 150, default_flags: bool = True,
                 normalize_includes: str = "auto") -> dict:
    if not file and code is None:
        return {"ok": False, "error": "Pass either file or code."}
    tmpdir = Path(tempfile.mkdtemp(prefix="pawnforge-"))
    if code is not None:
        # Snippets live in a private temp dir; the project's gamemodes/ and include
        # dirs are on the include path, so quoted includes still resolve.
        src = tmpdir / "snippet.pwn"
        src.write_text(code, encoding="utf-8")
    else:
        src = Path(file).expanduser()
        if not src.is_absolute() and project_dir:
            src = Path(project_dir) / src
        src = src.resolve()
        if not src.is_file():
            return {"ok": False, "error": f"Source file not found: {src}"}
    proj = project_dir or str(src.parent)
    root = find_root(proj)

    try:
        comp = find_compiler(str(root))
        has_pkg = (root / "pawn.json").exists() or (root / "pawn.yaml").exists()
        have_sampctl = shutil.which("sampctl") is not None
        if mode == "sampctl" and not have_sampctl:
            return {"ok": False, "error": "mode=sampctl but sampctl is not on PATH."}
        use_sampctl = code is None and have_sampctl and (mode == "sampctl" or (mode == "auto" and has_pkg))

        t0 = time.time()
        want_mirror = False
        if use_sampctl:
            rc, out, cmd = _sampctl_build(root, timeout)
            parsed = parse_output(out, root, src, include_dirs(root))
            amx = None
        else:
            if not comp.get("found") or comp.get("kind") != "pawncc":
                return {"ok": False, "error": "No working pawncc compiler found.", "compiler": comp}
            pawncc = Path(comp["path"])
            inc = include_dirs(root, includes)
            if output == "temp":
                amx = tmpdir / (src.stem + ".amx")
            elif output == "alongside":
                amx = src.with_suffix(".amx")
            else:
                amx = Path(output).expanduser().resolve()
                amx.parent.mkdir(parents=True, exist_ok=True)

            # Backslash include paths only resolve on Windows; elsewhere compile from a mirror.
            mapping: list[tuple[str, str]] = []
            build_src, build_inc = src, inc
            want_mirror = normalize_includes == "always" or (
                normalize_includes == "auto" and os.name != "nt"
                and _has_backslash_includes([src.parent, *inc]))
            if want_mirror:
                if code is not None:
                    # The snippet is our own temp file: normalise it in place instead of mirroring.
                    src.write_text(INCLUDE_DIRECTIVE.sub(
                        lambda m: m.group(1) + m.group(2).replace("\\", "/") + m.group(3), code), encoding="utf-8")
                else:
                    src_root = src.parent
                    m_src = _mirror_tree(src_root)
                    mapping.append((str(m_src), str(src_root)))
                    build_src = m_src / src.name
                build_inc = []
                for d in inc:
                    md = _mirror_tree(d)
                    mapping.append((str(md), str(d)))
                    build_inc.append(md)

            args = [str(pawncc), str(build_src), f"-o{amx}", "-d3"]
            for d in build_inc:
                args.append(f"-i{d}")
            if default_flags:
                args += [f for f in DEFAULT_FLAGS if f not in (flags or [])]
            if compat:
                args.append("-Z")
            for k, v in (defines or {}).items():
                args.append(f"{k}={v}" if v not in (None, "", True) else f"{k}=")
            args += [f for f in (flags or []) if isinstance(f, str)]
            r = subprocess.run(args, cwd=build_src.parent, capture_output=True, text=True, timeout=timeout,
                               env=_env_for(pawncc))
            rc, out, cmd = r.returncode, (r.stdout or "") + (r.stderr or ""), args
            if mapping:
                # Longest mirror prefix first so nested include dirs map correctly.
                for mp, orig in sorted(mapping, key=lambda x: -len(x[0])):
                    out = out.replace(mp, orig)
            parsed = parse_output(out, src.parent, src, inc)
        elapsed = round(time.time() - t0, 2)

        diags = parsed["diagnostics"]
        errors = [d for d in diags if d["severity"] in ("error", "fatal")]
        warnings = [d for d in diags if d["severity"] == "warning"]
        by_code: dict[str, int] = {}
        for d in diags:
            by_code[f'{d["severity"]} {d["code"]}'] = by_code.get(f'{d["severity"]} {d["code"]}', 0) + 1
        ok = rc == 0 and not errors and (amx is None or amx.exists())
        res = {
            "ok": ok,
            "clean": ok and not warnings,
            "errors": len(errors),
            "warnings": len(warnings),
            "counts_by_code": by_code,
            "diagnostics": diags[:max_diagnostics],
            "truncated": len(diags) > max_diagnostics,
            "stack": parsed["stack"],
            "command": " ".join(cmd),
            "elapsed_s": elapsed,
            "compiler": comp if not use_sampctl else {"kind": "sampctl"},
        }
        if not use_sampctl and want_mirror:
            res["include_normalization"] = ("Backslash #include paths were normalised in a cached mirror so this "
                                            "non-Windows compiler can resolve them; your files were not modified.")
        if amx is not None and amx.exists() and output != "temp":
            res["amx"] = str(amx)
        elif amx is not None and amx.exists():
            res["amx"] = "(built to a temp file and discarded; pass output='alongside' to keep it)"
        if code is not None:
            for d in res["diagnostics"]:
                if d["file"] == str(src):
                    d["file"] = "<snippet>"
        if any(d["code"] == "100" for d in diags):
            res["next_step"] = ("An include could not be found. Check project_info for include_dirs, pass includes=[...], "
                                "or run `sampctl ensure` for sampctl projects.")
        elif any(d.get("in_include") for d in errors) and not compat:
            res["next_step"] = ("Errors come from an include file. Legacy SA-MP includes may need compat=true (-Z), "
                                "or the include is incompatible with the selected stdlib.")
        if not ok and not diags:
            res["raw_output"] = out[-4000:]
        return res
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Compilation timed out after {timeout}s."}
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
