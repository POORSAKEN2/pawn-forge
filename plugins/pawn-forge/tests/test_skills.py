import re
import subprocess
import sys
import unittest
from pathlib import Path

from helpers import PLUGIN

REPO_ROOT = PLUGIN.parent.parent
SKILLS_ROOT = REPO_ROOT / "skills"
PLUGIN_SKILLS_ROOT = PLUGIN / "skills"


class SkillsTest(unittest.TestCase):
    def _validate_skills_dir(self, root: Path, *, min_count: int = 11) -> None:
        dirs = sorted(p for p in root.iterdir() if p.is_dir())
        self.assertGreaterEqual(len(dirs), min_count, f"expected >= {min_count} skills in {root}")
        for d in dirs:
            skill_md = d / "SKILL.md"
            self.assertTrue(skill_md.is_file(), f"missing SKILL.md in {d}")
            text = skill_md.read_text(encoding="utf-8")
            m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
            self.assertIsNotNone(m, f"missing YAML frontmatter in {skill_md}")
            fm = m.group(1)
            name_m = re.search(r"^name:\s*(.+)$", fm, re.M)
            desc_m = re.search(r"^description:\s*(.+)$", fm, re.M)
            self.assertIsNotNone(name_m, f"missing name in {skill_md}")
            self.assertEqual(name_m.group(1).strip(), d.name)
            self.assertRegex(d.name, r"^[a-z0-9-]{1,64}$")
            self.assertIsNotNone(desc_m, f"missing description in {skill_md}")
            self.assertLessEqual(len(desc_m.group(1).strip()), 1024)
            self.assertNotIn("mcp__plugin_pawn-forge_pawn__", text)
            for link in re.findall(r"\[[^\]]+\]\(([^)#:]+\.(?:md|py))\)", text):
                self.assertTrue((d / link).exists(), f"broken link {link} in {skill_md}")
            if "scripts/pawnforge_exec.py" in text:
                self.assertTrue((d / "scripts" / "pawnforge_exec.py").is_file(), f"missing scripts/pawnforge_exec.py in {d}")

    def test_agensi_skill_frontmatter_and_links(self):
        self._validate_skills_dir(SKILLS_ROOT)

    def test_plugin_skill_frontmatter_and_links(self):
        self._validate_skills_dir(PLUGIN_SKILLS_ROOT)
        standards_md = (PLUGIN_SKILLS_ROOT / "pawn-standards" / "SKILL.md").read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n", standards_md, re.S)
        self.assertIsNotNone(m)
        fm = m.group(1)
        self.assertRegex(fm, re.compile(r"^user-invocable:\s*false\s*$", re.M))
        self.assertRegex(fm, re.compile(r"^paths:\s*.+$", re.M))

    def test_plugin_skills_in_sync(self):
        r = subprocess.run(
            [sys.executable, str(PLUGIN / "tools" / "sync_skills.py"), "--check"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
