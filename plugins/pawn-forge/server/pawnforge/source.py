"""Lightweight Pawn source model shared by the linter, migrator and converters.

This is deliberately not a full parser. Pawn is heavily macro-driven (YSI in
particular rewrites the language), so every analysis works on a *masked* copy
of the text where comments, and optionally string contents, are blanked out
while every character keeps its original offset. That makes regexes safe to
run without matching inside comments or strings, and keeps line numbers exact.
"""
from __future__ import annotations

import ast
import bisect
import re
from dataclasses import dataclass, field

IDENT = r"[A-Za-z_@][\w@]*"

# Built-in constants worth knowing when resolving array sizes.
BUILTIN_CONSTANTS = {
    "MAX_PLAYER_NAME": 24,
    "MAX_CHATBUBBLE_LENGTH": 144,
    "MAX_CLIENT_MESSAGE": 144,
    "MAX_PLAYERS": 1000,
    "MAX_VEHICLES": 2000,
    "MAX_ACTORS": 1000,
    "MAX_TEXT_DRAWS": 2048,
    "MAX_PLAYER_TEXT_DRAWS": 256,
    "MAX_3DTEXT_GLOBAL": 1024,
    "MAX_3DTEXT_PLAYER": 1024,
    "MAX_GANG_ZONES": 1024,
    "MAX_PICKUPS": 4096,
    "MAX_MENUS": 128,
    "MAX_PLAYER_ATTACHED_OBJECTS": 10,
    "true": 1,
    "false": 0,
}


def mask(code: str, *, strings: bool) -> str:
    """Blank comments (and string/char contents if `strings`) with spaces.

    Newlines are preserved and every character keeps its offset. Handles
    `//` and `/* */` comments, escaped strings, raw strings (`\\"...\\"`),
    packed strings (`!"..."`) and character literals.
    """
    out = list(code)
    i, n = 0, len(code)
    while i < n:
        c = code[i]
        nxt = code[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            while i < n and code[i] != "\n":
                out[i] = " "
                i += 1
            continue
        if c == "/" and nxt == "*":
            out[i] = out[i + 1] = " "
            i += 2
            while i < n and not (code[i] == "*" and i + 1 < n and code[i + 1] == "/"):
                if code[i] != "\n":
                    out[i] = " "
                i += 1
            if i < n:
                out[i] = " "
                if i + 1 < n:
                    out[i + 1] = " "
                i += 2
            continue
        if c == '"' or (c == "\\" and nxt == '"'):
            raw = c == "\\"
            i += 2 if raw else 1
            while i < n and code[i] != '"' and code[i] != "\n":
                if code[i] == "\\" and not raw and i + 1 < n and code[i + 1] != "\n":
                    if strings:
                        out[i] = out[i + 1] = " "
                    i += 2
                    continue
                if strings:
                    out[i] = " "
                i += 1
            i += 1  # closing quote
            continue
        if c == "'":
            j = i + 1
            # Character literal: 'a', '\n', '\''. Bail out if it does not close soon,
            # which also protects against apostrophes inside #pragma/#error text.
            if j < n and code[j] == "\\":
                j += 2
            else:
                j += 1
            if j < n and code[j] == "'":
                if strings:
                    for k in range(i + 1, j):
                        out[k] = " "
                i = j + 1
                continue
        i += 1
    return "".join(out)


def safe_eval(expr: str, consts: dict[str, int]) -> int | None:
    """Evaluate a small integer constant expression, or return None."""
    expr = expr.strip()
    if not expr:
        return None
    expr = re.sub(r"\bsizeof\b", "", expr)

    def repl(m):
        name = m.group(0)
        if name in consts:
            return str(consts[name])
        raise KeyError(name)

    try:
        expr2 = re.sub(IDENT, repl, expr)
    except KeyError:
        return None
    if not re.fullmatch(r"[\d\s+\-*/%()xXa-fA-F]+", expr2):
        return None
    try:
        node = ast.parse(expr2.replace("/", "//"), mode="eval")
    except SyntaxError:
        return None
    allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Add, ast.Sub,
               ast.Mult, ast.FloorDiv, ast.Mod, ast.USub, ast.UAdd)
    if not all(isinstance(x, allowed) for x in ast.walk(node)):
        return None
    try:
        v = eval(compile(node, "<expr>", "eval"), {"__builtins__": {}}, {})  # noqa: S307 - AST-whitelisted
    except Exception:
        return None
    return int(v) if isinstance(v, int) else None


@dataclass
class Call:
    name: str
    start: int            # offset of the function name
    open_paren: int
    close_paren: int      # -1 if unterminated
    args: list[tuple[int, int]]  # spans in the original text

    def arg(self, src: "Source", i: int) -> str | None:
        if i < len(self.args):
            a, b = self.args[i]
            return src.text[a:b].strip()
        return None


@dataclass
class Function:
    name: str
    kind: str        # public / stock / static / hook / command / timer / plain
    header_start: int
    body_start: int  # offset of "{"
    body_end: int    # offset of matching "}"


@dataclass
class ArrayDecl:
    name: str
    dims: list[str]
    sizes: list[int | None]
    offset: int
    local: bool
    static: bool


@dataclass
class Source:
    text: str
    path: str = "<memory>"
    nocomment: str = field(init=False)
    masked: str = field(init=False)
    _nl: list[int] = field(init=False, repr=False)
    functions: list[Function] = field(init=False)
    defines: dict[str, int] = field(init=False)
    arrays: list[ArrayDecl] = field(init=False)

    def __post_init__(self):
        self.text = self.text.replace("\r\n", "\n").replace("\r", "\n")
        self.nocomment = mask(self.text, strings=False)
        self.masked = mask(self.text, strings=True)
        self._nl = [i for i, ch in enumerate(self.text) if ch == "\n"]
        self.defines = self._collect_defines()
        self.functions = self._collect_functions()
        self.arrays = self._collect_arrays()

    # -------------------------------------------------------------- positions
    def line_of(self, offset: int) -> int:
        return bisect.bisect_left(self._nl, offset) + 1

    def col_of(self, offset: int) -> int:
        ln = self.line_of(offset)
        start = 0 if ln == 1 else self._nl[ln - 2] + 1
        return offset - start + 1

    def line_text(self, line: int) -> str:
        lines = self.text.split("\n")
        return lines[line - 1] if 0 < line <= len(lines) else ""

    # -------------------------------------------------------------- calls
    def calls(self, name_pattern: str) -> list[Call]:
        """All calls whose name matches `name_pattern` (regex, full-name)."""
        out = []
        for m in re.finditer(rf"(?<![\w@.:])(?:{name_pattern})\s*\(", self.masked):
            name = re.match(IDENT, self.masked[m.start():]).group(0)
            # Skip declarations: native/forward/stock/public/static/hook headers.
            before = self.masked[max(0, m.start() - 40):m.start()]
            if re.search(r"\b(native|forward|public|stock|hook|static|enum)\s+(\w+:)?\s*$", before):
                continue
            op = m.end() - 1
            close, args = self.split_args(op)
            out.append(Call(name, m.start(), op, close, args))
        return out

    def split_args(self, open_paren: int) -> tuple[int, list[tuple[int, int]]]:
        depth, i, start = 0, open_paren, open_paren + 1
        args: list[tuple[int, int]] = []
        t = self.masked
        n = len(t)
        while i < n:
            ch = t[i]
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
                if depth == 0:
                    if t[start:i].strip() or args:
                        args.append((start, i))
                    return i, args
            elif ch == "," and depth == 1:
                args.append((start, i))
                start = i + 1
            elif ch == ";" and depth <= 1:
                break
            i += 1
        return -1, args

    # -------------------------------------------------------------- structure
    def _collect_defines(self) -> dict[str, int]:
        consts = dict(BUILTIN_CONSTANTS)
        raw: dict[str, str] = {}
        for m in re.finditer(rf"^[ \t]*#define[ \t]+({IDENT})[ \t]+([^\n]+)", self.nocomment, re.M):
            raw[m.group(1)] = m.group(2).strip()
        for m in re.finditer(rf"\bconst\s+(?:{IDENT}:)?({IDENT})\s*=\s*([^;]+);", self.nocomment):
            raw.setdefault(m.group(1), m.group(2).strip())
        # Resolve iteratively so defines can reference earlier defines.
        for _ in range(4):
            for k, v in raw.items():
                if k in consts:
                    continue
                val = safe_eval(v.strip("()"), consts)
                if val is not None:
                    consts[k] = val
        return consts

    def _collect_functions(self) -> list[Function]:
        t = self.masked
        funcs: list[Function] = []
        depth = 0
        seg_start = 0
        stack: list[tuple[int, int]] = []
        i, n = 0, len(t)
        while i < n:
            ch = t[i]
            if ch == "#" and self._at_line_start(t, i):
                # Skip preprocessor line (with continuations).
                while i < n and t[i] != "\n":
                    if t[i] == "\\" and i + 1 < n and t[i + 1] == "\n":
                        i += 2
                        continue
                    i += 1
                if depth == 0:
                    seg_start = i
                continue
            if ch == "{":
                if depth == 0:
                    stack.append((seg_start, i))
                depth += 1
            elif ch == "}":
                depth = max(0, depth - 1)
                if depth == 0 and stack:
                    hs, bs = stack.pop()
                    header = t[hs:bs].strip()
                    fn = self._function_from_header(header, hs + (len(t[hs:bs]) - len(t[hs:bs].lstrip())), bs, i)
                    if fn:
                        funcs.append(fn)
                    seg_start = i + 1
            elif ch == ";" and depth == 0:
                seg_start = i + 1
            i += 1
        return funcs

    @staticmethod
    def _at_line_start(t: str, i: int) -> bool:
        k = i - 1
        while k >= 0 and t[k] in " \t":
            k -= 1
        return k < 0 or t[k] == "\n"

    @staticmethod
    def _function_from_header(header: str, hs: int, bs: int, be: int) -> Function | None:
        if not header or header.endswith("=") or re.search(r"\benum\b", header):
            return None
        cm = re.search(rf"(?i)\b(y?cmd|command|dialog|alias)\s*:\s*({IDENT})\s*\(.*\)\s*$", header, re.S)
        if cm:
            kind = "dialog" if cm.group(1).lower() == "dialog" else "command"
            return Function(name=f"{cm.group(1)}:{cm.group(2)}", kind=kind,
                            header_start=hs, body_start=bs, body_end=be)
        m = re.search(
            rf"(?:(public|stock|static|hook|forward|ptask|task|timer|remotefunc)\s+)?"
            rf"(?:(public|stock|static)\s+)?(?:{IDENT}:)?((?:{IDENT}::?)?{IDENT})\s*(?:\[[^\]]*\])?\s*\(.*\)\s*$",
            header, re.S,
        )
        if not m:
            return None
        name = m.group(3)
        kw = (m.group(1) or m.group(2) or "").lower()
        if re.match(r"(?i)(y?cmd|command|dialog):", name) or name.lower().startswith(("cmd:", "ycmd:")):
            kind = "command" if not name.lower().startswith("dialog") else "dialog"
        elif kw in ("ptask", "task", "timer"):
            kind = "timer"
        else:
            kind = kw or "plain"
        if re.fullmatch(r"(if|for|while|switch|else|do|return)", name):
            return None
        return Function(name=name, kind=kind, header_start=hs, body_start=bs, body_end=be)

    def function_at(self, offset: int) -> Function | None:
        for f in self.functions:
            if f.body_start <= offset <= f.body_end:
                return f
        return None

    def _collect_arrays(self) -> list[ArrayDecl]:
        out: list[ArrayDecl] = []
        t = self.masked
        for m in re.finditer(r"\b(new|static)\b(?!\s*\()", t):
            # Gather the declaration statement up to ';' at the same nesting level.
            j, depth = m.end(), 0
            while j < len(t):
                c = t[j]
                if c in "([{":
                    depth += 1
                elif c in ")]}":
                    if depth == 0:
                        break
                    depth -= 1
                elif c == ";" and depth == 0:
                    break
                elif c == "\n" and depth == 0 and not t[m.end():j].strip().endswith(","):
                    # Declarations without semicolons end at newline (when -; not forced).
                    if re.search(r"[\w\])}'\"]\s*$", t[m.end():j]) and not re.match(r"\s*[,=]", t[j:j + 3]):
                        break
                j += 1
            stmt_start = m.end()
            pieces, depth, last = [], 0, stmt_start
            for k in range(stmt_start, j):
                c = t[k]
                if c in "([{":
                    depth += 1
                elif c in ")]}":
                    depth -= 1
                elif c == "," and depth == 0:
                    pieces.append((last, k))
                    last = k + 1
            pieces.append((last, j))
            local = self.function_at(m.start()) is not None
            for a, b in pieces:
                seg = t[a:b]
                dm = re.match(rf"\s*(?:const\s+)?(?:{IDENT}:)?({IDENT})\s*((?:\[[^\]]*\])+)", seg)
                if not dm:
                    continue
                dims = re.findall(r"\[([^\]]*)\]", dm.group(2))
                sizes = [safe_eval(d, self.defines) if d.strip() else None for d in dims]
                if sizes and sizes[0] is None and not dims[0].strip():
                    # `new s[] = "text"` - size comes from the initialiser.
                    init = self.text[a:b]
                    sm = re.search(r'=\s*"((?:[^"\\]|\\.)*)"', init)
                    if sm:
                        sizes[0] = len(bytes(sm.group(1), "utf-8").decode("unicode_escape", "ignore")) + 1
                out.append(ArrayDecl(dm.group(1), dims, sizes, a + dm.start(1), local, m.group(1) == "static"))
        return out

    def array_size(self, name: str, at: int) -> int | None:
        """Declared first-dimension size of `name` visible at offset `at`."""
        name = name.strip()
        fn = self.function_at(at)
        locals_ = [d for d in self.arrays if d.name == name and d.local and fn
                   and fn.body_start <= d.offset <= at]
        if locals_:
            best = max(locals_, key=lambda d: d.offset)
        else:
            globals_ = [d for d in self.arrays if d.name == name and not d.local]
            if not globals_:
                return None
            before = [d for d in globals_ if d.offset <= at]
            best = max(before, key=lambda d: d.offset) if before else globals_[0]
        return best.sizes[0] if best.sizes else None

    def includes(self) -> list[str]:
        return [m.group(1).strip() for m in
                re.finditer(r'^[ \t]*#(?:try)?include[ \t]+[<"]([^>"]+)[>"]', self.nocomment, re.M)]


def string_literal_value(arg: str) -> str | None:
    """Return the content of a plain string-literal argument, or None."""
    arg = arg.strip()
    if arg.startswith("!"):
        arg = arg[1:].strip()
    m = re.fullmatch(r'"((?:[^"\\]|\\.)*)"', arg, re.S)
    return m.group(1) if m else None


def bare_identifier(arg: str | None) -> str | None:
    if arg is None:
        return None
    m = re.fullmatch(rf"\s*({IDENT})\s*", arg)
    return m.group(1) if m else None


def sizeof_target(arg: str | None) -> str | None:
    """`sizeof(x)` / `sizeof x` / `sizeof (x)` -> 'x' (first-dimension only)."""
    if arg is None:
        return None
    m = re.fullmatch(rf"\s*sizeof\s*\(?\s*({IDENT})\s*\)?\s*", arg)
    return m.group(1) if m else None
