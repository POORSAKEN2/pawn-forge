#!/usr/bin/env python3
"""Sync canonical Agensi skills under `skills/` into `plugins/pawn-forge/skills/`.

Also keeps `scripts/pawnforge_exec.py` in every tool-using skill synchronized with
`plugins/pawn-forge/tools/pawnforge_exec.py`.

Usage:
    python plugins/pawn-forge/tools/sync_skills.py          # apply sync
    python plugins/pawn-forge/tools/sync_skills.py --check  # exit 1 on any drift
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
PLUGIN_DIR = TOOLS_DIR.parent
REPO_ROOT = PLUGIN_DIR.parent.parent
SRC_SKILLS_DIR = REPO_ROOT / "skills"
DST_SKILLS_DIR = PLUGIN_DIR / "skills"
EXEC_SRC = TOOLS_DIR / "pawnforge_exec.py"

SKILL_MAP: dict[str, str] = {
    "pawn-standards": "pawn-standards",
    "pawn-build": "build",
    "pawn-audit": "audit",
    "pawn-debug-crash": "debug-crash",
    "pawn-migrate-openmp": "migrate-openmp",
    "pawn-modernize-storage": "modernize-storage",
    "pawn-test": "test",
    "pawn-textdraw": "textdraw",
    "pawn-roleplay": "roleplay",
    "pawn-anticheat": "anticheat",
    "pawn-ecosystem": "ecosystem",
}

PLUGIN_FRONTMATTER_EXTRAS: dict[str, list[str]] = {
    "pawn-standards": [
        'when_to_use: Any task touching .pwn or .inc files, SA-MP/open.mp scripting questions, "write a command/system/gamemode", reviewing Pawn snippets, choosing Pawn libraries.',
        'paths: "**/*.pwn, **/*.inc, **/pawn.json"',
        "user-invocable: false",
    ],
    "audit": ['argument-hint: "[path]"'],
    "build": ['argument-hint: "[file.pwn] [keep]"'],
    "debug-crash": ['argument-hint: "[log path]"'],
    "migrate-openmp": ['argument-hint: "[file.pwn | directory]"'],
    "modernize-storage": ['argument-hint: "[sqlite|mysql]"'],
    "test": ['argument-hint: "[server-dir] [module or behaviour to test]"'],
    "textdraw": ['argument-hint: "[export-file] [Prefix]"'],
    "roleplay": ['argument-hint: "[system or file]"'],
    "anticheat": ['argument-hint: "[system or file]"'],
    "ecosystem": ['argument-hint: "[library or file]"'],
}

_RENAMED_SKILLS = {src: dst for src, dst in SKILL_MAP.items() if src != dst}
_CROSS_REF_RE = re.compile(
    r"(?<![a-z0-9-])("
    + "|".join(re.escape(src) for src in sorted(_RENAMED_SKILLS, key=len, reverse=True))
    + r")(?![a-z0-9-])"
)
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.S)
_IGNORE_PARTS = {"__pycache__", ".DS_Store"}


def _is_ignored(rel: Path) -> bool:
    return any(part in _IGNORE_PARTS or part.endswith(".pyc") for part in rel.parts)


def _rewrite_cross_refs(text: str) -> str:
    return _CROSS_REF_RE.sub(lambda m: _RENAMED_SKILLS[m.group(1)], text)


def _transform_skill_md(text: str, target_name: str) -> str:
    text = text.replace("\r\n", "\n")
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError(f"Missing YAML frontmatter when syncing target {target_name}")
    fm, body = m.group(1), m.group(2)

    fm = re.sub(r"^name:\s*.+$", f"name: {target_name}", fm, count=1, flags=re.M)
    extras = PLUGIN_FRONTMATTER_EXTRAS.get(target_name, [])
    if extras:
        existing_keys = {
            line.split(":", 1)[0].strip()
            for line in fm.splitlines()
            if ":" in line and not line.startswith(" ")
        }
        additions = [line for line in extras if line.split(":", 1)[0].strip() not in existing_keys]
        if additions:
            fm = fm.rstrip("\n") + "\n" + "\n".join(additions)

    body = _rewrite_cross_refs(body)
    return f"---\n{fm}\n---\n{body}"


def _read_normalized_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if path.suffix in {".md", ".py", ".txt", ".json", ".yaml", ".yml"}:
        return data.replace(b"\r\n", b"\n")
    return data


def _build_expected_plugin_tree(exec_bytes: bytes) -> dict[Path, bytes]:
    expected: dict[Path, bytes] = {}
    for src_name, dst_name in SKILL_MAP.items():
        src_dir = SRC_SKILLS_DIR / src_name
        dst_dir = DST_SKILLS_DIR / dst_name
        if not src_dir.is_dir():
            raise FileNotFoundError(f"Missing canonical skill directory: {src_dir}")

        skill_md_path = src_dir / "SKILL.md"
        skill_text = skill_md_path.read_text(encoding="utf-8")
        uses_exec = "scripts/pawnforge_exec.py" in skill_text or (src_dir / "scripts" / "pawnforge_exec.py").is_file()

        for src_file in sorted(src_dir.rglob("*")):
            if not src_file.is_file():
                continue
            rel = src_file.relative_to(src_dir)
            if _is_ignored(rel):
                continue
            dst_file = dst_dir / rel
            if rel.as_posix() == "SKILL.md":
                expected[dst_file] = _transform_skill_md(skill_text, dst_name).encode("utf-8")
            elif rel.as_posix() == "scripts/pawnforge_exec.py":
                expected[dst_file] = exec_bytes
            elif src_file.suffix == ".md":
                md_text = src_file.read_text(encoding="utf-8").replace("\r\n", "\n")
                expected[dst_file] = _rewrite_cross_refs(md_text).encode("utf-8")
            else:
                expected[dst_file] = _read_normalized_bytes(src_file)

        if uses_exec:
            expected[dst_dir / "scripts" / "pawnforge_exec.py"] = exec_bytes

    return expected


def _build_expected_src_exec(exec_bytes: bytes) -> dict[Path, bytes]:
    expected: dict[Path, bytes] = {}
    for src_name in SKILL_MAP:
        src_dir = SRC_SKILLS_DIR / src_name
        skill_md_path = src_dir / "SKILL.md"
        if not skill_md_path.is_file():
            continue
        skill_text = skill_md_path.read_text(encoding="utf-8")
        exec_path = src_dir / "scripts" / "pawnforge_exec.py"
        if "scripts/pawnforge_exec.py" in skill_text or exec_path.is_file():
            expected[exec_path] = exec_bytes
    return expected


def _prune_empty_dirs(root: Path) -> None:
    if not root.is_dir():
        return
    for d in sorted((p for p in root.rglob("*") if p.is_dir()), reverse=True):
        if not any(d.iterdir()):
            d.rmdir()


def sync(check: bool = False) -> bool:
    """Sync `skills/` -> `plugins/pawn-forge/skills/` and `pawnforge_exec.py`.

    When ``check=True``, no files are modified; returns ``True`` if everything
    is in sync and ``False`` otherwise.
    """
    if not EXEC_SRC.is_file():
        raise FileNotFoundError(f"Missing source script: {EXEC_SRC}")
    exec_bytes = _read_normalized_bytes(EXEC_SRC)

    issues: list[str] = []

    # 1. Sync pawnforge_exec.py into canonical root skills/
    src_exec_targets = _build_expected_src_exec(exec_bytes)
    for target, content in sorted(src_exec_targets.items()):
        if not target.is_file() or _read_normalized_bytes(target) != content:
            rel = target.relative_to(REPO_ROOT).as_posix()
            if check:
                issues.append(f"out of sync: {rel}")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)

    # 2. Sync skills/ -> plugins/pawn-forge/skills/
    expected_plugin = _build_expected_plugin_tree(exec_bytes)
    existing_plugin: set[Path] = set()
    if DST_SKILLS_DIR.is_dir():
        for p in DST_SKILLS_DIR.rglob("*"):
            if p.is_file() and not _is_ignored(p.relative_to(DST_SKILLS_DIR)):
                existing_plugin.add(p)

    for target, content in sorted(expected_plugin.items()):
        rel = target.relative_to(REPO_ROOT).as_posix()
        if not target.is_file():
            if check:
                issues.append(f"missing: {rel}")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
        elif _read_normalized_bytes(target) != content:
            if check:
                issues.append(f"drifted: {rel}")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)

    orphaned = sorted(existing_plugin - set(expected_plugin.keys()))
    for extra in orphaned:
        rel = extra.relative_to(REPO_ROOT).as_posix()
        if check:
            issues.append(f"orphaned: {rel}")
        else:
            extra.unlink()

    if not check:
        _prune_empty_dirs(DST_SKILLS_DIR)
        return True

    if issues:
        for item in issues:
            print(item, file=sys.stderr)
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync canonical skills/ to plugins/pawn-forge/skills/.")
    parser.add_argument("--check", action="store_true", help="Check whether files are in sync without modifying them.")
    args = parser.parse_args(argv)
    ok = sync(check=args.check)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
