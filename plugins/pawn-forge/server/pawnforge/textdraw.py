"""Convert raw TextDraw editor exports into a clean, self-contained module.

Accepts the output of the common editors (Zamaroht's editor, iTD, nTD and
similar): `X = TextDrawCreate(...)` / `X[playerid] = CreatePlayerTextDraw(...)`
followed by property calls. Produces one include with:
  * arrays instead of dozens of loose globals,
  * named index constants so code can update individual TextDraws,
  * Create / Destroy / Show / Hide functions for global and per-player sets,
  * guarded creation so repeated calls never leak TextDraws,
  * open.mp names and tagged constants when target="openmp".
"""
from __future__ import annotations

import re

from . import data
from .migrate import ALIGN_NAMES, FONT_NAMES, _omp_native_params
from .source import IDENT, Source

SKIP = {"TextDrawCreate", "CreatePlayerTextDraw", "TextDrawShowForPlayer", "TextDrawHideForPlayer",
        "TextDrawShowForAll", "TextDrawHideForAll", "TextDrawDestroy", "PlayerTextDrawShow",
        "PlayerTextDrawHide", "PlayerTextDrawDestroy"}
CANVAS_W, CANVAS_H = 640.0, 448.0


def _fmt_num(s: str) -> str:
    s = s.strip()
    if re.fullmatch(r"-?\d+\.\d+", s):
        v = float(s)
        out = f"{v:.6f}".rstrip("0")
        return out + "0" if out.endswith(".") else out
    return s


def _const_name(prefix: str, var: str) -> str:
    base = re.sub(r"\[.*$", "", var)
    base = re.sub(r"[^A-Za-z0-9_]", "_", base)
    return f"{prefix.upper()}_{base.upper()}"


def convert_textdraws(code: str, prefix: str = "TD", target: str = "openmp", ysi_hooks: bool = False) -> dict:
    if not re.fullmatch(IDENT, prefix or ""):
        return {"ok": False, "error": "prefix must be a valid Pawn identifier, e.g. HUD or Speedo."}
    src = Source(code)
    t = src.masked
    globals_: list[dict] = []
    players: list[dict] = []
    by_key: dict[str, dict] = {}
    warnings: list[str] = []

    for m in re.finditer(rf"({IDENT}(?:\s*\[[^\]]*\])*)\s*=\s*(TextDrawCreate|CreatePlayerTextDraw)\s*\(", t):
        lhs = re.sub(r"\s+", "", m.group(1))
        is_player = m.group(2) == "CreatePlayerTextDraw"
        call = next((c for c in src.calls(m.group(2)) if c.start == m.start(2)), None)
        if call is None:
            continue
        args = [src.text[a:b].strip() for a, b in call.args]
        if is_player:
            args = args[1:]
        if len(args) < 3:
            warnings.append(f"Line {src.line_of(m.start())}: could not read the arguments of {m.group(2)}.")
            continue
        key = re.sub(r"\[(?:playerid|i|pid|id)\]", "", lhs)
        td = {"var": lhs, "key": key, "player": is_player, "x": _fmt_num(args[0]), "y": _fmt_num(args[1]),
              "text": args[2], "props": [], "line": src.line_of(m.start())}
        by_key[key] = td
        (players if is_player else globals_).append(td)

    if not by_key:
        return {"ok": False, "error": "No TextDrawCreate / CreatePlayerTextDraw assignments found in the input."}

    prop_calls = src.calls(r"(?:Player)?TextDraw[\w@]*")
    deps = data.load("omp_deprecations")
    sigs = _omp_native_params()
    for c in prop_calls:
        if c.name in SKIP:
            continue
        is_player = c.name.startswith("PlayerTextDraw")
        args = [src.text[a:b].strip() for a, b in c.args]
        td_arg = args[1] if is_player and len(args) > 1 else (args[0] if args else "")
        key = re.sub(r"\[(?:playerid|i|pid|id)\]", "", re.sub(r"\s+", "", td_arg))
        td = by_key.get(key)
        if td is None:
            continue
        rest = args[2:] if is_player else args[1:]
        name = c.name
        if target == "openmp":
            d = deps.get(name)
            if d and d.get("safe_rename") and d.get("replacement"):
                name = d["replacement"]
            tags = sigs.get(name, [])
            offset = 2 if is_player else 1
            new_rest = []
            for i, a in enumerate(rest):
                tag = tags[i + offset] if i + offset < len(tags) else None
                v = a.strip()
                if tag == "bool" and v in ("0", "1"):
                    v = "true" if v == "1" else "false"
                elif tag == "TEXT_DRAW_FONT" and v.isdigit() and int(v) in FONT_NAMES:
                    v = FONT_NAMES[int(v)]
                elif tag == "TEXT_DRAW_ALIGN" and v.isdigit() and int(v) in ALIGN_NAMES:
                    v = ALIGN_NAMES[int(v)]
                else:
                    v = _fmt_num(v)
                new_rest.append(v)
            rest = new_rest
        else:
            rest = [_fmt_num(a) for a in rest]
        td["props"].append((name, rest))

    # ---------------------------------------------------------------- validation
    for td in globals_ + players:
        try:
            x, y = float(td["x"]), float(td["y"])
            if not (0 <= x <= CANVAS_W and 0 <= y <= CANVAS_H):
                warnings.append(f"{td['var']} is positioned at ({x}, {y}), outside the 640x448 TextDraw canvas.")
        except ValueError:
            pass
        names = {p[0] for p in td["props"]}
        selectable = any(p[0].endswith("SetSelectable") and p[1] and p[1][-1] in ("1", "true") for p in td["props"])
        if selectable and not any(n.endswith("TextSize") for n in names):
            warnings.append(f"{td['var']} is selectable but has no TextSize call; its clickable area will be wrong.")
    if len(globals_) > 2048:
        warnings.append(f"{len(globals_)} global TextDraws exceeds the 2048 server limit.")
    if len(players) > 256:
        warnings.append(f"{len(players)} player TextDraws exceeds the 256 per-player limit.")

    # ---------------------------------------------------------------- generation
    P = prefix
    inv_g = "INVALID_TEXT_DRAW"
    inv_p = "INVALID_PLAYER_TEXT_DRAW"
    out: list[str] = []
    w = out.append
    w(f"// {P} TextDraws - generated by pawn-forge from an editor export.")
    w(f"// {len(globals_)} global and {len(players)} per-player TextDraws. Target: {target}.")
    w(f"#if defined _inc_{P.lower()}_textdraws")
    w("\t#endinput")
    w("#endif")
    w(f"#define _inc_{P.lower()}_textdraws")
    w("")
    if globals_:
        w("enum {")
        for i, td in enumerate(globals_):
            w(f"\t{_const_name(P, td['key'])}{' = 0' if i == 0 else ''},")
        w(f"\t{P.upper()}_GLOBAL_COUNT")
        w("};")
        w(f"static Text:{P}_gTD[{P.upper()}_GLOBAL_COUNT] = {{{inv_g}, ...}};")
        w(f"static bool:{P}_gCreated = false;")
        w("")
    if players:
        w("enum {")
        for i, td in enumerate(players):
            w(f"\t{_const_name(P + '_P', td['key'])}{' = 0' if i == 0 else ''},")
        w(f"\t{P.upper()}_PLAYER_COUNT")
        w("};")
        w(f"static PlayerText:{P}_pTD[MAX_PLAYERS][{P.upper()}_PLAYER_COUNT];")
        w(f"static bool:{P}_pCreated[MAX_PLAYERS];")
        w("")

    def emit(td, idx_expr, is_player):
        if is_player:
            ref = f"{P}_pTD[playerid][{idx_expr}]"
            w(f"\t{ref} = CreatePlayerTextDraw(playerid, {td['x']}, {td['y']}, {td['text']});")
            for name, rest in td["props"]:
                w(f"\t{name}(playerid, {ref}{', ' if rest else ''}{', '.join(rest)});")
        else:
            ref = f"{P}_gTD[{idx_expr}]"
            w(f"\t{ref} = TextDrawCreate({td['x']}, {td['y']}, {td['text']});")
            for name, rest in td["props"]:
                w(f"\t{name}({ref}{', ' if rest else ''}{', '.join(rest)});")

    if globals_:
        w(f"stock {P}_CreateGlobal()")
        w("{")
        w(f"\tif ({P}_gCreated) return 0;")
        for td in globals_:
            emit(td, _const_name(P, td["key"]), False)
        w(f"\t{P}_gCreated = true;")
        w("\treturn 1;")
        w("}")
        w("")
        w(f"stock {P}_DestroyGlobal()")
        w("{")
        w(f"\tif (!{P}_gCreated) return 0;")
        w(f"\tfor (new i = 0; i < sizeof ({P}_gTD); i++)")
        w("\t{")
        w(f"\t\tTextDrawDestroy({P}_gTD[i]);")
        w(f"\t\t{P}_gTD[i] = {inv_g};")
        w("\t}")
        w(f"\t{P}_gCreated = false;")
        w("\treturn 1;")
        w("}")
        w("")
        for verb, native in (("Show", "TextDrawShowForPlayer"), ("Hide", "TextDrawHideForPlayer")):
            w(f"stock {P}_{verb}Global(playerid)")
            w("{")
            w(f"\tif (!{P}_gCreated) return 0;")
            w(f"\tfor (new i = 0; i < sizeof ({P}_gTD); i++) {native}(playerid, {P}_gTD[i]);")
            w("\treturn 1;")
            w("}")
            w("")
    if players:
        w(f"stock {P}_CreatePlayer(playerid)")
        w("{")
        w(f"\tif ({P}_pCreated[playerid]) {P}_DestroyPlayer(playerid);")
        for td in players:
            emit(td, _const_name(P + "_P", td["key"]), True)
        w(f"\t{P}_pCreated[playerid] = true;")
        w("\treturn 1;")
        w("}")
        w("")
        w(f"stock {P}_DestroyPlayer(playerid)")
        w("{")
        w(f"\tif (!{P}_pCreated[playerid]) return 0;")
        w(f"\tfor (new i = 0; i < {P.upper()}_PLAYER_COUNT; i++)")
        w("\t{")
        w(f"\t\tPlayerTextDrawDestroy(playerid, {P}_pTD[playerid][i]);")
        w(f"\t\t{P}_pTD[playerid][i] = {inv_p};")
        w("\t}")
        w(f"\t{P}_pCreated[playerid] = false;")
        w("\treturn 1;")
        w("}")
        w("")
        for verb, native in (("Show", "PlayerTextDrawShow"), ("Hide", "PlayerTextDrawHide")):
            w(f"stock {P}_{verb}Player(playerid)")
            w("{")
            w(f"\tif (!{P}_pCreated[playerid]) return 0;")
            w(f"\tfor (new i = 0; i < {P.upper()}_PLAYER_COUNT; i++) {native}(playerid, {P}_pTD[playerid][i]);")
            w("\treturn 1;")
            w("}")
            w("")
        w(f"stock PlayerText:{P}_GetPlayerTD(playerid, index)")
        w("{")
        w(f"\tif (!{P}_pCreated[playerid] || index < 0 || index >= {P.upper()}_PLAYER_COUNT) return {inv_p};")
        w(f"\treturn {P}_pTD[playerid][index];")
        w("}")
        w("")
    if globals_:
        w(f"stock Text:{P}_GetGlobalTD(index)")
        w("{")
        w(f"\tif (!{P}_gCreated || index < 0 || index >= {P.upper()}_GLOBAL_COUNT) return {inv_g};")
        w(f"\treturn {P}_gTD[index];")
        w("}")
        w("")
    if ysi_hooks:
        if globals_:
            w(f"hook OnGameModeInit() {{ {P}_CreateGlobal(); return 1; }}")
            w(f"hook OnGameModeExit() {{ {P}_DestroyGlobal(); return 1; }}")
        if players:
            w(f"hook OnPlayerConnect(playerid) {{ {P}_CreatePlayer(playerid); return 1; }}")
            w(f"hook OnPlayerDisconnect(playerid, reason) {{ {P}_DestroyPlayer(playerid); return 1; }}")
        w("")
    usage = []
    if globals_:
        usage.append(f"OnGameModeInit: {P}_CreateGlobal();   OnGameModeExit: {P}_DestroyGlobal();")
        usage.append(f"Show/hide: {P}_ShowGlobal(playerid) / {P}_HideGlobal(playerid)")
    if players:
        usage.append(f"OnPlayerConnect: {P}_CreatePlayer(playerid);   OnPlayerDisconnect: {P}_DestroyPlayer(playerid);")
        usage.append(f"Update one: PlayerTextDrawSetString(playerid, {P}_GetPlayerTD(playerid, "
                     f"{_const_name(P + '_P', players[0]['key'])}), \"...\");")
    if ysi_hooks:
        usage.append("Requires #include <YSI_Coding\\y_hooks> before this file; create/destroy calls are hooked.")
    return {
        "ok": True,
        "globals": len(globals_),
        "player": len(players),
        "warnings": warnings,
        "code": "\n".join(out).rstrip() + "\n",
        "usage": usage,
        "index_constants": {td["var"]: _const_name(P if not td["player"] else P + "_P", td["key"])
                            for td in globals_ + players},
    }
