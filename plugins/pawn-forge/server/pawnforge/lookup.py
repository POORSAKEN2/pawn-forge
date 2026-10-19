"""Deterministic lookup of in-game IDs so generated code never invents them."""
from __future__ import annotations

import difflib
import re

from . import data

KINDS = ("vehicle", "weapon", "skin", "interior", "animation", "limit")


def _fuzzy(query: str, items: list[dict], keys: tuple[str, ...], limit: int) -> list[dict]:
    q = query.lower().strip()
    scored = []
    for it in items:
        best = 0.0
        for k in keys:
            val = str(it.get(k) or "").lower()
            if not val:
                continue
            if q == val:
                score = 1.0
            elif q in val:
                score = 0.9 - 0.001 * (len(val) - len(q))
            else:
                score = difflib.SequenceMatcher(None, q, val).ratio() * 0.8
            best = max(best, score)
        if best >= 0.45:
            scored.append((best, it))
    scored.sort(key=lambda x: -x[0])
    if scored and scored[0][0] >= 0.85:
        # A direct hit exists: drop the weak fuzzy tail so the answer is unambiguous.
        scored = [s for s in scored if s[0] >= 0.85]
    return [it for _, it in scored[:limit]]


def lookup(kind: str, query: str | int | None = None, limit: int = 10, library: str | None = None) -> dict:
    kind = (kind or "").lower().strip()
    if kind not in KINDS:
        return {"error": f"Unknown kind '{kind}'. Use one of: {', '.join(KINDS)}."}
    q = "" if query is None else str(query).strip()
    limit = max(1, min(int(limit or 10), 200))

    if kind == "vehicle":
        items = data.load("vehicles")
        if q.isdigit():
            hit = [v for v in items if v["id"] == int(q)]
            if hit:
                return {"kind": kind, "valid": True, "results": hit}
            return {"kind": kind, "valid": False,
                    "message": f"{q} is not a valid vehicle model. Valid models are 400-611."}
        if not q:
            return {"kind": kind, "count": len(items), "range": [400, 611],
                    "results": items[:limit], "note": "Pass a name or category to search."}
        return {"kind": kind, "results": _fuzzy(q, items, ("name", "model_name", "category"), limit)}

    if kind == "weapon":
        items = data.load("weapons")
        if re.fullmatch(r"-?\d+", q):
            hit = [w for w in items if w["id"] == int(q)]
            if hit:
                w = hit[0]
                return {"kind": kind, "valid": True, "givable": w["givable"], "results": hit}
            return {"kind": kind, "valid": False,
                    "message": f"{q} is not a weapon or death-reason ID (19-21 are unused; givable weapons are 0-18, 22-46)."}
        if not q:
            return {"kind": kind, "results": items[:limit], "note": "Pass a name, constant or ID."}
        return {"kind": kind, "results": _fuzzy(q, items, ("name", "constant"), limit)}

    if kind == "skin":
        items = data.load("skins")
        if re.fullmatch(r"-?\d+", q):
            i = int(q)
            hit = [s for s in items if s["id"] == i]
            if hit:
                return {"kind": kind, "valid": True, "results": hit}
            msg = "Skin 74 is the invalid skin in SA-MP and open.mp." if i == 74 else \
                "Valid skins are 0-311, except 74."
            return {"kind": kind, "valid": False, "message": msg}
        if not q:
            return {"kind": kind, "count": len(items), "note": "Valid skins: 0-311 except 74. Pass a name to search."}
        return {"kind": kind, "results": _fuzzy(q, items, ("name", "model_name", "location"), limit)}

    if kind == "interior":
        items = data.load("interiors")
        if re.fullmatch(r"\d+", q):
            return {"kind": kind, "results": [x for x in items if x["interior"] == int(q)][:limit],
                    "note": "Set SetPlayerInterior before SetPlayerPos; use a unique virtual world per instance."}
        if not q:
            sections = sorted({x["section"] for x in items if x["section"]})
            return {"kind": kind, "count": len(items), "sections": sections}
        return {"kind": kind, "results": _fuzzy(q, items, ("name", "section"), limit),
                "note": "Set SetPlayerInterior before SetPlayerPos; use a unique virtual world per instance."}

    if kind == "animation":
        items = data.load("animations")
        lib = (library or "").upper()
        if lib and lib not in data.animation_libraries():
            close = difflib.get_close_matches(lib, data.animation_libraries(), n=5)
            return {"kind": kind, "valid": False, "message": f"Unknown animation library '{library}'.",
                    "did_you_mean": close}
        pool = [a for a in items if not lib or a["library"].upper() == lib]
        if lib and q:
            exact = data.animation_index().get((lib, q.upper()))
            if exact:
                return {"kind": kind, "valid": True, "results": [exact],
                        "usage": f'ApplyAnimation(playerid, "{exact["library"]}", "{exact["name"]}", 4.1, false, false, false, false, 0);'}
        if not q:
            if lib:
                return {"kind": kind, "library": lib, "count": len(pool), "results": pool[:limit]}
            libs = sorted({a["library"] for a in items})
            return {"kind": kind, "libraries": libs, "count": len(items)}
        res = _fuzzy(q, pool, ("name", "description"), limit)
        return {"kind": kind, "results": res, "note": "Library and animation names are case-insensitive. "
                "Preload a library once per player (ApplyAnimation with a 0.0 delta) before first use."}

    if kind == "limit":
        rows = data.load("limits")
        if q:
            rows = [r for r in rows if q.lower() in r[0].lower()]
        return {"kind": kind, "results": [{"type": r[0], "limits": r[1:]} for r in rows][:limit * 4]}

    return {"error": "unreachable"}
