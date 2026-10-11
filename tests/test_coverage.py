"""Replacement: tests swapped for different tests while the function stays.

Each case is a two-commit repository read by the detector; nothing is run.
"""

from __future__ import annotations

from pr_witness import coverage, git_ops
from pr_witness.compare import Severity
from pr_witness.gate import decide
from pr_witness.witness import witness

from .test_git_ops import commit, repo  # noqa: F401

CONFTEST = "import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).parent))\n"

SRC = '''
class ExtractError(Exception):
    pass


def layout(path):
    return {"path": path}


def extract(path, dm=0.0):
    if path is None:
        raise ExtractError("no file")
    return {"toa": dm * 2}


def shift(a, b):
    return a + b
'''

TESTS = '''
import pytest

from ex import ExtractError, extract, layout


def test_layout():
    assert layout("f")["path"] == "f"


def test_extract_end_to_end():
    assert extract("f", dm=2.0)["toa"] == 4.0


def test_extract_needs_a_file():
    with pytest.raises(ExtractError):
        extract(None)
'''

# The replacement: the helper goes, the end-to-end test goes with it, and
# what is left calls `extract` only to watch it fail.
SRC_AFTER = SRC.replace('def layout(path):\n    return {"path": path}\n\n\n', "")
TESTS_AFTER = '''
import pytest

from ex import ExtractError, extract, shift


def test_shift_is_addition():
    assert shift(1, 2) == 3


def test_extract_fails_loudly():
    with pytest.raises(ExtractError):
        extract(None)
'''


def detect(repo, base):
    head = git_ops.resolve("HEAD", cwd=repo)
    return coverage.detect_coverage_replaced(repo, base, head, git_ops.changed_files(base, head, cwd=repo))


def test_a_function_whose_real_tests_were_swapped_for_an_error_path_is_reported(repo):  # noqa: F811
    base = commit(repo, "init", {"ex.py": SRC, "tests/test_ex.py": TESTS})
    commit(repo, "reconcile", {"ex.py": SRC_AFTER, "tests/test_ex.py": TESTS_AFTER})
    (finding,) = detect(repo, base)
    assert finding.signal == "coverage_replaced" and finding.severity is Severity.MEDIUM
    # `extract` still exists and is called only inside raises; `layout` was
    # removed with its test, which is cleanup and not reported.
    assert finding.tests == ["ex.py::extract"]
    assert "only where an error is expected" in finding.summary


def test_a_function_removed_together_with_its_tests_is_cleanup(repo):  # noqa: F811
    base = commit(repo, "init", {"ex.py": SRC, "tests/test_ex.py": TESTS})
    without_layout_test = TESTS.replace('def test_layout():\n    assert layout("f")["path"] == "f"\n\n\n', "") \
                               .replace("from ex import ExtractError, extract, layout", "from ex import ExtractError, extract")
    commit(repo, "drop layout", {"ex.py": SRC_AFTER, "tests/test_ex.py": without_layout_test})
    assert detect(repo, base) == []


def test_a_function_still_called_by_a_test_the_change_did_not_touch_is_not_reported(repo):  # noqa: F811
    other = "from ex import extract\n\n\ndef test_other():\n    assert extract('g', dm=1.0)['toa'] == 2.0\n"
    base = commit(repo, "init", {"ex.py": SRC, "tests/test_ex.py": TESTS, "tests/test_other.py": other})
    commit(repo, "reconcile", {"ex.py": SRC_AFTER, "tests/test_ex.py": TESTS_AFTER})
    assert detect(repo, base) == []


def test_a_test_file_that_merely_moved_is_not_reported(repo):  # noqa: F811
    base = commit(repo, "init", {"ex.py": SRC, "tests/test_ex.py": TESTS})
    commit(repo, "move", {"tests/test_ex.py": None, "tests/unit/test_extract.py": TESTS})
    assert detect(repo, base) == []


def test_imports_through_a_module_alias_are_followed(repo):  # noqa: F811
    tests = "import ex as e\n\n\ndef test_it():\n    assert e.extract('f', dm=1.0)['toa'] == 2.0\n"
    after = "import ex as e\n\n\ndef test_it():\n    assert e.shift(1, 1) == 2\n"
    base = commit(repo, "init", {"ex.py": SRC, "tests/test_ex.py": tests})
    commit(repo, "swap", {"tests/test_ex.py": after})
    (finding,) = detect(repo, base)
    assert finding.tests == ["ex.py::extract"] and "error is expected" not in finding.summary


def test_a_change_that_touches_no_python_test_reads_nothing(repo):  # noqa: F811
    base = commit(repo, "init", {"ex.py": SRC, "tests/test_ex.py": TESTS})
    commit(repo, "code only", {"ex.py": SRC + "\n\nX = 1\n"})
    assert detect(repo, base) == []


def test_end_to_end_a_replacement_is_a_review_and_the_gate_holds_it(repo):  # noqa: F811
    """What the cross-run alone called cleanup: the old file no longer imports."""
    base = commit(repo, "init", {"conftest.py": CONFTEST, "ex.py": SRC, "tests/test_ex.py": TESTS})
    commit(repo, "reconcile", {"ex.py": SRC_AFTER, "tests/test_ex.py": TESTS_AFTER})
    ev = witness(repo=repo, base=base, runner_name="pytest", timeout=300)
    assert "coverage_replaced" in {f.signal for f in ev.findings}
    assert ev.verdict == "review"
    assert decide(ev, "require-ack").exit_code == 1
    assert decide(ev, "require-ack", approved=True).exit_code == 0
