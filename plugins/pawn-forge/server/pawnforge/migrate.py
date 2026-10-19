"""SA-MP -> open.mp migration assistant.

Everything here is derived from the open.mp standard library itself:
  * deprecations and renames come from its `#pragma deprecated` declarations,
  * tag fixes come from the tagged parameter lists of its native signatures,
  * callback headers come from its `forward` declarations.

Edits are classified as `safe` (mechanical and behaviour-preserving, applied
when write != "none") or `manual` (needs a human decision; reported only).
"""
from __future__ import annotations

import difflib
import functools
import re
from pathlib import Path

from . import data
from .source import IDENT, Source

PLUGIN_NOTES = {
    "pawn.cmd": "Pawn.CMD: use the open.mp build (3.4.0-omp or newer) and put it in components/, not plugins/.",
    "pawn.raknet": "Pawn.RakNet: use the open.mp build and put it in components/.",
    "sscanf2": "sscanf: use 2.13.8+ and put it in components/ on open.mp.",
    "ysf": "YSF is not needed on open.mp: most of its natives are built in. Remove it and recompile.",
    "fcnpc": "FCNPC is replaced by the official open.mp NPC component; port to the built-in NPC natives.",
    "sky": "SKY is not supported on open.mp; use Pawn.RakNet instead.",
    "discord-connector": "discord-connector: use the open.mp-compatible release and put it in components/.",
    "sampvoice": "sampvoice: use the -omp release and put it in components/.",
}
FONT_NAMES = {0: "TEXT_DRAW_FONT_0", 1: "TEXT_DRAW_FONT_1", 2: "TEXT_DRAW_FONT_2", 3: "TEXT_DRAW_FONT_3",
              4: "TEXT_DRAW_FONT_SPRITE_DRAW", 5: "TEXT_DRAW_FONT_MODEL_PREVIEW"}
ALIGN_NAMES = {1: "TEXT_DRAW_ALIGN_LEFT", 2: "TEXT_DRAW_ALIGN_CENTER", 3: "TEXT_DRAW_ALIGN_RIGHT"}


def _split_params(params: str) -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in params:
        if ch in "{[(":
            depth += 1
        elif ch in "}])":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def _param_tag(p: str) -> str | None:
    p = re.sub(r"^\s*const\s+", "", p)
    m = re.match(rf"\s*&?\s*({IDENT}):", p)
    return m.group(1) if m else None


@functools.lru_cache(maxsize=None)
def _omp_native_params() -> dict[str, list[str | None]]:
    out = {}
    for n in data.load("natives"):
        if n["library"] != "open.mp" or n.get("deprecated"):
            continue
        params = _split_params(n["params"])
        if any(p.strip().startswith("...") or "OPEN_MP_TAGS:..." in p for p in params):
            params = [p for p in params if "..." not in p]
        out[n["name"]] = [_param_tag(p) for p in params]
    return out


@functools.lru_cache(maxsize=None)
def _omp_callbacks() -> dict[str, list[str]]:
    return {c["name"]: _split_params(c["params"]) for c in data.load("callbacks") if c["library"] == "open.mp"}


def _weapon_by_id() -> dict[int, str]:
    return {w["id"]: w["constant"] for w in data.load("weapons") if w.get("constant") and w.get("givable")}


class Migration:
    def __init__(self, src: Source):
        self.s = src
        self.items: list[dict] = []
        self.edits: list[tuple[int, int, str]] = []

    def add(self, kind: str, offset: int, message: str, *, safe: bool, edit: tuple[int, int, str] | None = None,
            replacement: str | None = None):
        line = self.s.line_of(offset)
        item = {"kind": kind, "line": line, "message": message, "safe": safe,
                "source": self.s.line_text(line).strip()[:240]}
        if replacement:
            item["replacement"] = replacement
        self.items.append(item)
        if safe and edit:
            self.edits.append(edit)

    # -------------------------------------------------------------- includes & plugins
    def includes(self):
        for m in re.finditer(r"^[ \t]*#[ \t]*include[ \t]*<a_samp>", self.s.nocomment, re.M):
            a = self.s.text.index("<a_samp>", m.start())
            self.add("include", m.start(), "Replace #include <a_samp> with #include <open.mp>.", safe=True,
                     edit=(a, a + len("<a_samp>"), "<open.mp>"), replacement="#include <open.mp>")
        incs = [i.lower().replace("\\", "/") for i in self.s.includes()]
        for inc in incs:
            base = inc.split("/")[-1]
            if base in PLUGIN_NOTES:
                self.add("plugin", 0, PLUGIN_NOTES[base], safe=False)
            if inc.startswith("ysi/") and not inc.startswith(("ysi_", "ysi/ysi_")):
                self.add("library", 0, f"#include <{inc}> uses YSI 4 paths. open.mp recommends YSI 5.x "
                                       "(e.g. <YSI_Coding\\y_hooks>, <YSI_Data\\y_iterate>).", safe=False)

    # -------------------------------------------------------------- deprecations
    def deprecations(self):
        deps = data.load("omp_deprecations")
        names = [n for n in deps if not n.startswith(("@", "PLAYER_STATE_"))]
        if not names:
            return
        pat = re.compile(r"(?<![\w@.])(" + "|".join(sorted(map(re.escape, names), key=len, reverse=True)) + r")\b")
        for m in pat.finditer(self.s.masked):
            before = self.s.masked[max(0, m.start() - 30):m.start()]
            if re.search(r"\b(native|forward)\s+(\w+:)?\s*$", before):
                continue
            name = m.group(1)
            d = deps[name]
            rep = d.get("replacement")
            if name in ("GetPlayerPoolSize", "GetVehiclePoolSize", "GetActorPoolSize"):
                const = {"GetPlayerPoolSize": "MAX_PLAYERS", "GetVehiclePoolSize": "MAX_VEHICLES",
                         "GetActorPoolSize": "MAX_ACTORS"}[name]
                self.add("deprecated", m.start(), f"{name} is broken and deprecated. Loop to {const} with '<' "
                         f"(not '<='), or iterate with foreach.", safe=False, replacement=const)
                continue
            if d.get("safe_rename") and rep:
                self.add("rename", m.start(), f"{name} -> {rep}", safe=True,
                         edit=(m.start(), m.end(), rep), replacement=rep)
            else:
                self.add("deprecated", m.start(), f"{name}: {d['message']}", safe=False, replacement=rep)

    # -------------------------------------------------------------- tags
    def tags(self):
        sigs = _omp_native_params()
        weapons = _weapon_by_id()
        if not sigs:
            return
        names = "|".join(sorted(map(re.escape, sigs), key=len, reverse=True))
        for c in self.s.calls(names):
            tags = sigs.get(c.name)
            if not tags:
                continue
            for i, (a, b) in enumerate(c.args):
                if i >= len(tags) or not tags[i]:
                    continue
                arg = self.s.text[a:b]
                lit = arg.strip()
                if not re.fullmatch(r"-?\d+", lit):
                    continue
                v = int(lit)
                tag = tags[i]
                rep = None
                if tag == "bool" and v in (0, 1):
                    rep = "true" if v else "false"
                elif tag == "WEAPON" and v in weapons:
                    rep = weapons[v]
                elif tag == "TEXT_DRAW_FONT" and v in FONT_NAMES:
                    rep = FONT_NAMES[v]
                elif tag == "TEXT_DRAW_ALIGN" and v in ALIGN_NAMES:
                    rep = ALIGN_NAMES[v]
                elif tag == "Float":
                    rep = f"{v}.0"
                if rep:
                    s = a + (len(arg) - len(arg.lstrip()))
                    self.add("tag", s, f"{c.name} argument {i + 1} is tagged {tag}: use {rep} instead of {lit} "
                                       f"(avoids warning 213).", safe=True, edit=(s, s + len(lit), rep),
                             replacement=rep)

    # -------------------------------------------------------------- callbacks
    def callbacks(self):
        cbs = _omp_callbacks()
        for fn in self.s.functions:
            if fn.name not in cbs or fn.kind not in ("public", "hook", "plain"):
                continue
            header = self.s.text[fn.header_start:fn.body_start]
            m = re.search(r"\((.*)\)\s*$", header, re.S)
            if not m:
                continue
            user = _split_params(m.group(1))
            omp = cbs[fn.name]
            if len(user) != len(omp):
                self.add("callback", fn.header_start, f"{fn.name} has {len(user)} parameters; open.mp declares "
                         f"{len(omp)}: forward {fn.name}({', '.join(omp)}).", safe=False)
                continue
            new_params, changed = [], False
            for up, op in zip(user, omp):
                ut, ot = _param_tag(up), _param_tag(op)
                if ut == ot:
                    new_params.append(up)
                    continue
                name = re.sub(rf"^\s*(const\s+)?&?\s*(?:{IDENT}:)?", "", up).strip()
                prefix = "const " if re.match(r"\s*const\b", op) else ""
                amp = "&" if "&" in op.split(":")[0] else ""
                new_params.append(f"{prefix}{amp}{ot + ':' if ot else ''}{name}")
                changed = True
            if changed:
                a = fn.header_start + m.start(1)
                b = fn.header_start + m.end(1)
                rep = ", ".join(new_params)
                self.add("callback", fn.header_start,
                         f"{fn.name} parameter tags differ from open.mp (error 025): ({rep})",
                         safe=True, edit=(a, b, rep), replacement=rep)

    def run(self) -> None:
        self.includes()
        self.deprecations()
        self.tags()
        self.callbacks()

    def apply(self) -> str:
        text = self.s.text
        edits = sorted(set(self.edits), key=lambda e: e[0])
        out, last = [], 0
        for a, b, rep in edits:
            if a < last:
                continue  # overlapping edit; keep the first
            out.append(text[last:a])
            out.append(rep)
            last = b
        out.append(text[last:])
        return "".join(out)


def migrate_openmp(file: str | None = None, code: str | None = None, write: str = "none",
                   max_items: int = 400) -> dict:
    if code is None:
        if not file:
            return {"ok": False, "error": "Pass file or code."}
        p = Path(file).expanduser().resolve()
        if not p.is_file():
            return {"ok": False, "error": f"File not found: {p}"}
        text = p.read_text(encoding="utf-8", errors="replace")
    else:
        p, text = None, code
    src = Source(text, str(p) if p else "<snippet>")
    mig = Migration(src)
    mig.run()
    new_text = mig.apply()
    diff = "".join(difflib.unified_diff(src.text.splitlines(True), new_text.splitlines(True),
                                        fromfile=str(p or "a"), tofile=str(p or "b") + " (open.mp)", n=1))
    res = {
        "ok": True,
        "safe_changes": sum(1 for i in mig.items if i["safe"]),
        "manual_changes": sum(1 for i in mig.items if not i["safe"]),
        "items": sorted(mig.items, key=lambda i: (i["safe"], i["line"]))[:max_items],
        "diff": diff[:60000],
        "next_steps": [
            "Compile with the open.mp includes (compile tool) and fix the remaining warnings.",
            "Move components (Pawn.CMD, sscanf, Pawn.RakNet...) to components/ and list legacy plugins in "
            "config.json pawn.legacy_plugins.",
            "Run lint to catch runtime issues the compiler cannot see (format specifier mismatches etc.).",
        ],
    }
    if write in ("in_place", "copy") and p is not None and mig.edits:
        target = p if write == "in_place" else p.with_name(p.stem + ".omp" + p.suffix)
        if write == "in_place":
            backup = p.with_suffix(p.suffix + ".samp.bak")
            if not backup.exists():
                backup.write_text(text, encoding="utf-8")
            res["backup"] = str(backup)
        target.write_text(new_text, encoding="utf-8")
        res["written"] = str(target)
    if write == "return" or (code is not None and write not in ("none",)):
        res["migrated_code"] = new_text
    return res
