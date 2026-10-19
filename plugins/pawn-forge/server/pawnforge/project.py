"""Project discovery: layout, platform (SA-MP vs open.mp), include dirs, plugins."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

INCLUDE_DIR_CANDIDATES = ("include", "includes", "qawno/include", "pawno/include", "inc", "pawn/include")
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".vscode", ".idea", "logs"}


def find_root(start: str | os.PathLike) -> Path:
    """Walk up from `start` to the nearest directory that looks like a Pawn project root."""
    p = Path(start).resolve()
    if p.is_file():
        p = p.parent
    markers = ("pawn.json", "pawn.yaml", "config.json", "server.cfg", "gamemodes", "qawno", "pawno")
    for cand in [p, *p.parents]:
        if any((cand / m).exists() for m in markers):
            return cand
        if cand.parent == cand:
            break
    return p


def _sampctl_package(root: Path) -> dict | None:
    for name in ("pawn.json", "pawn.yaml"):
        f = root / name
        if f.exists():
            if name.endswith(".json"):
                try:
                    return json.loads(f.read_text(encoding="utf-8"))
                except Exception:
                    return {"_unparsed": name}
            return {"_yaml": name}
    return None


def include_dirs(project_dir: str | os.PathLike | None, extra: list[str] | None = None) -> list[Path]:
    """Ordered, de-duplicated include directories for a project."""
    dirs: list[Path] = []
    if project_dir:
        root = find_root(project_dir)
        for c in INCLUDE_DIR_CANDIDATES:
            d = root / c
            if d.is_dir():
                dirs.append(d)
        deps = root / "dependencies"
        if deps.is_dir():
            # sampctl places each dependency in dependencies/<repo>, sometimes with an
            # include path inside it; add every directory that directly holds .inc files.
            for sub in sorted(deps.rglob("*")):
                if sub.is_dir() and any(f.suffix == ".inc" for f in sub.iterdir() if f.is_file()):
                    dirs.append(sub)
        gm = root / "gamemodes"
        if gm.is_dir():
            dirs.append(gm)
    for e in extra or []:
        if e and Path(e).is_dir():
            dirs.append(Path(e))
    for e in filter(None, os.environ.get("PAWNFORGE_INCLUDE_PATHS", "").split(os.pathsep)):
        if Path(e).is_dir():
            dirs.append(Path(e))
    seen, out = set(), []
    for d in dirs:
        r = d.resolve()
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def detect_platform(root: Path, includes: list[str]) -> dict:
    inc = {i.lower() for i in includes}
    evidence = []
    if "open.mp" in inc:
        evidence.append("#include <open.mp>")
    if (root / "config.json").exists():
        evidence.append("config.json present (open.mp server config)")
    if any((root / n).exists() for n in ("omp-server", "omp-server.exe")):
        evidence.append("omp-server binary present")
    if (root / "qawno").exists():
        evidence.append("qawno/ present (open.mp distribution)")
    samp = []
    if "a_samp" in inc:
        samp.append("#include <a_samp>")
    if (root / "server.cfg").exists():
        samp.append("server.cfg present")
    if any((root / n).exists() for n in ("samp-server.exe", "samp03svr")):
        samp.append("samp-server binary present")
    if (root / "pawno").exists():
        samp.append("pawno/ present")
    platform = "open.mp" if evidence and len(evidence) >= len(samp) else ("sa-mp" if samp else "unknown")
    return {"platform": platform, "openmp_evidence": evidence, "samp_evidence": samp}


def _plugins(root: Path) -> dict:
    out: dict = {}
    cfg = root / "config.json"
    if cfg.exists():
        try:
            j = json.loads(cfg.read_text(encoding="utf-8"))
            out["config.json"] = {
                "legacy_plugins": j.get("pawn", {}).get("legacy_plugins", []),
                "main_scripts": j.get("pawn", {}).get("main_scripts", []),
                "side_scripts": j.get("pawn", {}).get("side_scripts", []),
            }
        except Exception as exc:  # malformed JSON is itself a useful finding
            out["config.json"] = {"error": f"could not parse: {exc}"}
    scfg = root / "server.cfg"
    if scfg.exists():
        for line in scfg.read_text(encoding="utf-8", errors="replace").splitlines():
            k, _, v = line.partition(" ")
            if k in ("plugins", "gamemode0", "filterscripts"):
                out.setdefault("server.cfg", {})[k] = v.strip()
    comps = root / "components"
    if comps.is_dir():
        out["components"] = sorted(p.name for p in comps.iterdir() if p.is_file())
    plug = root / "plugins"
    if plug.is_dir():
        out["plugins_dir"] = sorted(p.name for p in plug.iterdir() if p.is_file())
    return out


def project_info(project_dir: str) -> dict:
    from .compiler import find_compiler  # local import to avoid a cycle

    root = find_root(project_dir)
    pkg = _sampctl_package(root)
    sources = []
    for base in ("gamemodes", "filterscripts", "."):
        d = root / base
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.pwn")):
            sources.append(str(f.relative_to(root)))
    main = None
    if pkg and isinstance(pkg, dict) and pkg.get("entry"):
        main = pkg["entry"]
    elif any(s.startswith("gamemodes") for s in sources):
        main = next(s for s in sources if s.startswith("gamemodes"))
    elif sources:
        main = sources[0]
    includes: list[str] = []
    if main and (root / main).exists():
        txt = (root / main).read_text(encoding="utf-8", errors="replace")
        includes = re.findall(r'^[ \t]*#(?:try)?include[ \t]+[<"]([^>"]+)[>"]', txt, re.M)
    libs = {
        "ysi": any(i.lower().startswith("ysi") for i in includes),
        "streamer": any("streamer" in i.lower() for i in includes),
        "mysql": any(i.lower() in ("a_mysql", "mysql") for i in includes),
        "sscanf": any("sscanf" in i.lower() for i in includes),
        "pawn.cmd": any(i.lower() == "pawn.cmd" for i in includes),
        "zcmd/izcmd": any(i.lower() in ("zcmd", "izcmd") for i in includes),
        "dini/dfile": any(i.lower() in ("dini", "dini2", "dfile", "dutils", "dudb", "dof2") for i in includes),
        "y_ini": any("y_ini" in i.lower() for i in includes),
        "crashdetect": any("crashdetect" in i.lower() for i in includes),
    }
    comp = find_compiler(str(root))
    return {
        "root": str(root),
        "sampctl_package": pkg,
        "sources": sources[:200],
        "main_script": main,
        "includes_in_main": includes,
        "libraries_detected": {k: v for k, v in libs.items() if v},
        "include_dirs": [str(d) for d in include_dirs(root)],
        "server": _plugins(root),
        **detect_platform(root, includes),
        "compiler": comp,
    }
