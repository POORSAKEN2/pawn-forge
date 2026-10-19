#!/usr/bin/env python3
"""Regenerate pawn-forge's bundled reference data from upstream sources.

Maintainer tool: end users never need to run this. Every JSON file in
server/data/ is derived from an upstream source, so the plugin never ships
hand-typed IDs, signatures or deprecations.

Usage:
    python3 tools/build_data.py --sources /path/to/checkouts

Expected checkouts under --sources (shallow clones are fine):
    omp-stdlib/              github.com/openmultiplayer/omp-stdlib
    omp-web/                 github.com/openmultiplayer/web  (frontend/docs/scripting/resources)
    samp-streamer-plugin/    github.com/samp-incognito/samp-streamer-plugin
    SA-MP-MySQL/             github.com/pBlueG/SA-MP-MySQL
    sscanf/                  github.com/Y-Less/sscanf
    Pawn.CMD/                github.com/katursis/Pawn.CMD
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "server" / "data"


def git_rev(path: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), "log", "-1", "--format=%H %cs"], text=True
        ).strip()
    except Exception:
        return "unknown"


def md_rows(text: str):
    """Yield the cells of every markdown table body row."""
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|") or set(s) <= set("|- :"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        yield cells


def strip_md(s: str) -> str:
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)          # images
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)        # links
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip()


# --------------------------------------------------------------------------- docs tables
def build_vehicles(res: Path):
    out = []
    pat = re.compile(
        r"Vehicle Model ID:\s*(\d+).*?Vehicle Name:\s*([^<]+?)\s*<br/>\s*Category:\s*([^<]+?)\s*<br/>"
        r"(?:.*?Model name:\s*([^<|]+?)\s*(?:<br/>|\|))?(?:.*?Number of seats:\s*(\d+))?",
        re.S,
    )
    for line in (res / "vehicleid.md").read_text(encoding="utf-8").splitlines():
        m = pat.search(line)
        if m:
            out.append({
                "id": int(m.group(1)),
                "name": m.group(2).strip(),
                "category": m.group(3).strip(),
                "model_name": (m.group(4) or "").strip() or None,
                "seats": int(m.group(5)) if m.group(5) else None,
            })
    out.sort(key=lambda v: v["id"])
    return out


def build_weapons(res: Path):
    out = []
    for cells in md_rows((res / "weaponids.md").read_text(encoding="utf-8")):
        if len(cells) < 9 or not cells[3].isdigit():
            continue
        name = strip_md(cells[0])
        out.append({
            "id": int(cells[3]),
            "name": name,
            "constant": cells[2] if cells[2] not in ("-", "") else None,
            "slot": int(cells[4]) if cells[4].isdigit() else None,
            "model": int(cells[5]) if cells[5].isdigit() else None,
            "clip": cells[6] if cells[6] not in ("-", "") else None,
            "givable": "can not be used in" not in cells[8] and "Only usable in" not in cells[8],
            "notes": strip_md(cells[8]) if cells[8] not in ("-", "") else None,
        })
    out.sort(key=lambda w: w["id"])
    return out


def build_skins(res: Path):
    out = []
    for cells in md_rows((res / "skins.md").read_text(encoding="utf-8")):
        if len(cells) < 6 or not cells[0].isdigit():
            continue
        out.append({
            "id": int(cells[0]),
            "model_name": cells[2],
            "name": strip_md(cells[3]),
            "location": strip_md(cells[4]),
            "gender": cells[5],
        })
    out.sort(key=lambda s: s["id"])
    return out


def build_interiors(res: Path):
    out, section = [], None
    for line in (res / "interiorids.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
            continue
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5 or not cells[1].lstrip("-").isdigit():
            continue
        try:
            x, y, z = (float(cells[i]) for i in (2, 3, 4))
        except ValueError:
            continue
        out.append({"section": section, "name": strip_md(cells[0]),
                    "interior": int(cells[1]), "x": x, "y": y, "z": z})
    return out


def build_animations(res: Path):
    out = []
    for cells in md_rows((res / "animations.md").read_text(encoding="utf-8")):
        if len(cells) < 6 or not cells[0].isdigit():
            continue
        out.append({
            "library": cells[1],
            "name": cells[2],
            "frames": int(cells[3]) if cells[3].isdigit() else None,
            "duration": float(cells[4]) if re.fullmatch(r"[\d.]+", cells[4]) else None,
            "description": strip_md(cells[5]),
            "notes": strip_md(cells[6]) if len(cells) > 6 and cells[6] else None,
        })
    return out


def build_limits(res: Path):
    rows = []
    for cells in md_rows((res / "limits.md").read_text(encoding="utf-8")):
        if len(cells) >= 2 and cells[0] not in ("Type",):
            rows.append([strip_md(c) for c in cells])
    return rows


# --------------------------------------------------------------------------- include scanning
NATIVE_RE = re.compile(
    r"^\s*native\s+(?:(?P<tag>[A-Za-z_@][\w@]*):)?(?P<name>[A-Za-z_@][\w@]*)\s*\((?P<params>.*?)\)\s*"
    r"(?:=\s*(?P<alias>[A-Za-z_@][\w@]*))?\s*;"
)
FORWARD_RE = re.compile(
    r"^\s*forward\s+(?:(?P<tag>[A-Za-z_@][\w@]*):)?(?P<name>On[A-Za-z_]\w*)\s*\((?P<params>.*?)\)\s*;"
)
DEPRECATED_RE = re.compile(r"#pragma\s+deprecated\s*(?P<msg>.*)$")
DECL_RE = re.compile(
    r"^\s*(?:native|forward|stock|const)\s+(?:[A-Za-z_@][\w@]*:)?(?P<name>[A-Za-z_@][\w@]*)\s*[(=;]"
)
ALIAS_RE = re.compile(r"=\s*(?P<alias>[A-Za-z_@][\w@]*)\s*;\s*$")
USE_RE = re.compile(r"Use\s+`(?P<rep>[A-Za-z_@][\w@]*)`")


def doc_summary(lines, idx):
    """Return the <summary> of the doc comment that ends just above line idx."""
    j = idx - 1
    block = []
    while j >= 0 and lines[j].strip().startswith(("#", "")) and len(block) < 80:
        s = lines[j].strip()
        if s.startswith("#pragma deprecated") or s.startswith("#if") or s.startswith("#else") or s.startswith("#endif") or s == "":
            j -= 1
            if s == "" and block:
                break
            continue
        if s.startswith(("*", "/**", "*/", "///")):
            block.append(s)
            j -= 1
            continue
        break
    text = " ".join(reversed(block))
    text = re.sub(r"^/\*\*|\*/$", "", text)
    text = re.sub(r"(^|\s)\*(\s|$)", " ", text)
    text = text.replace("///", " ")
    m = re.search(r"<summary>(.*?)</summary>", text, re.S)
    summary = m.group(1) if m else ""
    summary = re.sub(r"<[^>]+>", "", summary)
    summary = re.sub(r"\s+", " ", summary).strip()
    return summary[:300] or None


def scan_includes(paths, library, root: Path):
    natives, callbacks = [], []
    for p in paths:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        pending_dep = None
        for i, line in enumerate(lines):
            d = DEPRECATED_RE.search(line)
            if d:
                pending_dep = (d.group("msg").strip(), i)
                continue
            m = NATIVE_RE.match(line)
            f = None if m else FORWARD_RE.match(line)
            hit = m or f
            if not hit:
                continue
            dep = None
            if pending_dep and i - pending_dep[1] <= 8:
                dep = pending_dep[0]
            pending_dep = None
            entry = {
                "name": hit.group("name"),
                "library": library,
                "signature": line.strip().rstrip(";").replace("\t", " "),
                "return_tag": hit.group("tag"),
                "params": re.sub(r"\s+", " ", hit.group("params").strip()),
                "file": str(p.relative_to(root)),
                "line": i + 1,
            }
            if m and m.group("alias"):
                entry["internal_name"] = m.group("alias")
            summ = doc_summary(lines, i)
            if summ:
                entry["summary"] = summ
            if dep:
                entry["deprecated"] = dep
            (natives if m else callbacks).append(entry)
    # De-duplicate (#if/#else branches declare the same symbol twice); keep the
    # non-deprecated declaration when both exist.
    def dedupe(items):
        best = {}
        for e in items:
            k = e["name"]
            if k not in best or (best[k].get("deprecated") and not e.get("deprecated")):
                best[k] = e
        return sorted(best.values(), key=lambda e: e["name"].lower())
    return dedupe(natives), dedupe(callbacks)


def build_omp_deprecations(stdlib: Path):
    out = {}
    for p in sorted(stdlib.glob("*.inc")):
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        for i, line in enumerate(lines):
            d = DEPRECATED_RE.search(line)
            if not d:
                continue
            msg = d.group("msg").strip()
            for j in range(i + 1, min(i + 9, len(lines))):
                dm = DECL_RE.match(lines[j])
                if not dm:
                    continue
                name = dm.group("name")
                am = ALIAS_RE.search(lines[j])
                um = USE_RE.search(msg)
                rep = um.group("rep") if um else None
                kind = lines[j].split()[0]
                rec = {
                    "replacement": rep,
                    "message": msg,
                    "kind": kind,
                    "file": p.name,
                    "line": j + 1,
                    # A pure rename is safe to apply mechanically when the old
                    # declaration is an alias of the replacement native, or when the
                    # header documents it as a spelling-only change.
                    "safe_rename": bool(rep) and (
                        (am is not None and am.group("alias") == rep)
                        or "MIXED_SPELLINGS" in msg
                        or "LEGACY_SCRIPTING_API" in msg
                    ),
                }
                if name.startswith("PLAYER_STATE_"):
                    rec["safe_rename"] = False
                out.setdefault(name, rec)
                break
    # The spelling-only renames are declared as aliases in the opposite direction
    # (e.g. `native TextDrawColour(...) = TextDrawColor;`), which the loop above
    # already classifies through MIXED_SPELLINGS.
    return dict(sorted(out.items(), key=lambda kv: kv[0].lower()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", required=True, type=Path)
    args = ap.parse_args()
    src = args.sources
    res = src / "omp-web" / "frontend" / "docs" / "scripting" / "resources"
    DATA.mkdir(parents=True, exist_ok=True)

    def dump(name, obj):
        (DATA / name).write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        n = len(obj) if hasattr(obj, "__len__") else "-"
        print(f"  wrote {name:28s} {n} entries")

    dump("vehicles.json", build_vehicles(res))
    dump("weapons.json", build_weapons(res))
    dump("skins.json", build_skins(res))
    dump("interiors.json", build_interiors(res))
    dump("animations.json", build_animations(res))
    dump("limits.json", build_limits(res))
    dump("omp_deprecations.json", build_omp_deprecations(src / "omp-stdlib"))

    libs = {
        "open.mp": (sorted((src / "omp-stdlib").glob("*.inc")), src / "omp-stdlib"),
        "streamer": ([src / "samp-streamer-plugin" / "streamer.inc"], src / "samp-streamer-plugin"),
        "mysql-r41": ([src / "SA-MP-MySQL" / "a_mysql.inc.in"], src / "SA-MP-MySQL"),
        "sscanf": ([src / "sscanf" / "sscanf2.inc"], src / "sscanf"),
        "pawn.cmd": ([src / "Pawn.CMD" / "src" / "Pawn.CMD.inc"], src / "Pawn.CMD"),
    }
    all_natives, all_callbacks = [], []
    for lib, (paths, root) in libs.items():
        n, c = scan_includes([p for p in paths if p.exists()], lib, root)
        print(f"  scanned {lib:10s} natives={len(n):4d} callbacks={len(c)}")
        all_natives += n
        all_callbacks += c
    dump("natives.json", all_natives)
    dump("callbacks.json", all_callbacks)

    sources = {
        "generated": _dt.date.today().isoformat(),
        "omp-stdlib": git_rev(src / "omp-stdlib"),
        "omp-web (docs/scripting/resources)": git_rev(src / "omp-web"),
        "samp-streamer-plugin": git_rev(src / "samp-streamer-plugin"),
        "SA-MP-MySQL": git_rev(src / "SA-MP-MySQL"),
        "sscanf": git_rev(src / "sscanf"),
        "Pawn.CMD": git_rev(src / "Pawn.CMD"),
    }
    dump("sources.json", sources)


if __name__ == "__main__":
    main()
