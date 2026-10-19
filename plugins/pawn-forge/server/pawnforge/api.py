"""Exact API signatures from real include files.

Two sources, merged:
  1. The bundled index (open.mp stdlib, Streamer, MySQL R41, sscanf2, Pawn.CMD),
     generated from the upstream headers by tools/build_data.py.
  2. The project's own include directories, scanned on demand so the answer
     matches the exact library versions the project compiles against.
"""
from __future__ import annotations

import difflib
import os
import re
from pathlib import Path

from . import data
from .project import include_dirs

_DECL = re.compile(
    r"^\s*(?P<kind>native|forward)\s+(?:(?P<tag>[A-Za-z_@][\w@]*):)?(?P<name>[A-Za-z_@][\w@]*)\s*\((?P<params>.*?)\)\s*"
    r"(?:=\s*[A-Za-z_@][\w@]*)?\s*;"
)
_cache: dict[str, tuple[float, list[dict]]] = {}


def _scan_project(project_dir: str) -> list[dict]:
    out: list[dict] = []
    for d in include_dirs(project_dir):
        for root, _dirs, files in os.walk(d):
            for fn in files:
                if not fn.lower().endswith((".inc", ".pwn")):
                    continue
                p = Path(root) / fn
                try:
                    mtime = p.stat().st_mtime
                except OSError:
                    continue
                key = str(p)
                if key in _cache and _cache[key][0] == mtime:
                    out.extend(_cache[key][1])
                    continue
                entries: list[dict] = []
                try:
                    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
                except OSError:
                    continue
                for i, line in enumerate(lines):
                    m = _DECL.match(line)
                    if m:
                        entries.append({
                            "name": m.group("name"),
                            "library": f"project:{p.name}",
                            "signature": line.strip().rstrip(";"),
                            "file": str(p),
                            "line": i + 1,
                        })
                _cache[key] = (mtime, entries)
                out.extend(entries)
    return out


def api_lookup(name: str | None = None, query: str | None = None, library: str | None = None,
               project_dir: str | None = None, limit: int = 10) -> dict:
    limit = max(1, min(int(limit or 10), 50))
    bundled = data.load("natives") + data.load("callbacks")
    project = _scan_project(project_dir) if project_dir else []
    pool = project + bundled
    if library:
        lib = library.lower()
        pool = [e for e in pool if lib in e["library"].lower()]

    if name:
        exact = [e for e in pool if e["name"] == name]
        if not exact:
            exact = [e for e in pool if e["name"].lower() == name.lower()]
        if exact:
            # Project headers win: they reflect the versions actually in use.
            exact.sort(key=lambda e: 0 if e["library"].startswith("project:") else 1)
            dep = data.load("omp_deprecations").get(exact[0]["name"])
            res = {"found": True, "results": exact[:limit]}
            if dep:
                res["openmp_deprecation"] = dep
            return res
        names = sorted({e["name"] for e in pool})
        close = difflib.get_close_matches(name, names, n=8, cutoff=0.6)
        return {"found": False,
                "message": f"No declaration named '{name}' in the bundled index"
                           + (" or the project's includes." if project_dir else ". Pass project_dir to also search the project's includes."),
                "did_you_mean": close}

    if query:
        q = query.lower()
        hits = [e for e in pool if q in e["name"].lower() or q in (e.get("summary") or "").lower()]
        hits.sort(key=lambda e: (0 if e["name"].lower().startswith(q) else 1, len(e["name"])))
        return {"count": len(hits), "results": hits[:limit]}

    libs: dict[str, int] = {}
    for e in pool:
        libs[e["library"]] = libs.get(e["library"], 0) + 1
    return {"libraries": libs, "sources": data.load("sources"),
            "note": "Pass name= for an exact signature or query= to search names and summaries."}
