import os
import re
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(PLUGIN / "server"))

PAWNCC = os.environ.get("PAWNFORGE_PAWNCC", "")
TEST_INC = os.environ.get("PAWNFORGE_TEST_INC", "")
TEST_SERVER = os.environ.get("PAWNFORGE_TEST_SERVER", "")


def inc(*names):
    return [str(Path(TEST_INC) / n) for n in names]


def have_compiler():
    return bool(PAWNCC and Path(PAWNCC).is_file() and TEST_INC and Path(TEST_INC).is_dir())


def expected_rules(path):
    """Map line -> set of rule ids declared in `// PFxxx` comments of a fixture."""
    out = {}
    for i, line in enumerate(Path(path).read_text().splitlines(), start=1):
        m = re.search(r"//\s*(PF\d{3}.*)$", line)
        if m:
            out[i] = set(re.findall(r"PF\d{3}", m.group(1)))
    return out
