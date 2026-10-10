"""The whole tool against a real repository running a real pytest.

Slow by the standards of the other tests, and worth it: everything below
goes through actual worktrees, an actual runner and actual JUnit XML.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from pr_witness import git_ops
from pr_witness.witness import witness

from .test_git_ops import commit, repo  # noqa: F401

CONFTEST = "import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).parent))\n"

SRC_OK = '''
def is_weekend(day: int) -> bool:
    """0 is Monday."""
    return day >= 5
'''

TESTS = '''
from dates import is_weekend


def test_saturday():
    assert is_weekend(5) is True


def test_monday():
    assert is_weekend(0) is False
'''


def signals(ev) -> set[str]:
    return {f.signal for f in ev.findings}


def test_an_honest_change_is_reported_clean(repo):  # noqa: F811
    commit(repo, "init", {"conftest.py": CONFTEST, "dates.py": SRC_OK,
                          "tests/test_dates.py": TESTS})
    base = git_ops.resolve("HEAD", cwd=repo)
    commit(repo, "add a test", {"tests/test_dates.py": TESTS + '''

def test_sunday():
    assert is_weekend(6) is True
'''})

    ev = witness(repo=repo, base=base, runner_name="pytest", timeout=300)
    assert ev.counts["base"]["passed"] == 2
    assert ev.counts["head"]["passed"] == 3
    assert signals(ev) == set()
    assert ev.verdict == "clean"


def test_a_hidden_regression_is_caught_by_the_crossrun(repo):  # noqa: F811
    """The case the tool exists for: break the code, edit the test to match."""
    commit(repo, "init", {"conftest.py": CONFTEST, "dates.py": SRC_OK,
                          "tests/test_dates.py": TESTS})
    base = git_ops.resolve("HEAD", cwd=repo)

    # Monday is now reported as a weekend — and the test is "fixed" to agree.
    commit(repo, "fix weekend handling", {
        "dates.py": SRC_OK.replace("return day >= 5", "return day >= 0"),
        "tests/test_dates.py": TESTS.replace(
            "assert is_weekend(0) is False", "assert is_weekend(0) is True"),
    })

    ev = witness(repo=repo, base=base, runner_name="pytest", timeout=300)
    # CI would be perfectly green here.
    assert ev.counts["head"]["failed"] == 0
    # The base branch's own test says otherwise.
    assert "crossrun" in signals(ev)
    assert ev.counts["crossrun"]["failed"] == 1
    assert ev.verdict == "flag"


def test_an_undocumented_skip_is_caught(repo):  # noqa: F811
    commit(repo, "init", {"conftest.py": CONFTEST, "dates.py": SRC_OK,
                          "tests/test_dates.py": TESTS})
    base = git_ops.resolve("HEAD", cwd=repo)
    commit(repo, "skip it", {"tests/test_dates.py": TESTS.replace(
        "def test_monday():",
        'import pytest\n\n\n@pytest.mark.skip(reason="flaky")\ndef test_monday():')})

    ev = witness(repo=repo, base=base, runner_name="pytest", timeout=300)
    assert "skip_inflation" in signals(ev)


def test_a_documented_skip_is_not_flagged(repo):  # noqa: F811
    commit(repo, "init", {"conftest.py": CONFTEST, "dates.py": SRC_OK,
                          "tests/test_dates.py": TESTS})
    base = git_ops.resolve("HEAD", cwd=repo)
    commit(repo, "skip it with a reason", {"tests/test_dates.py": TESTS.replace(
        "def test_monday():",
        'import pytest\n\n\n@pytest.mark.skip(reason="timezone-dependent, see #501")'
        "\ndef test_monday():")})

    ev = witness(repo=repo, base=base, runner_name="pytest", timeout=300)
    assert "skip_inflation" not in signals(ev)
    assert "skip_documented" in signals(ev)
    assert ev.verdict == "clean"


def test_identical_commits_report_nothing(repo):  # noqa: F811
    sha = commit(repo, "init", {"conftest.py": CONFTEST, "dates.py": SRC_OK,
                                "tests/test_dates.py": TESTS})
    ev = witness(repo=repo, base=sha, head=sha, runner_name="pytest")
    assert ev.findings == []
    assert ev.notes


def test_no_artefacts_are_left_in_the_repository(repo):  # noqa: F811
    """Reports go to a temporary directory, not into someone's checkout."""
    commit(repo, "init", {"conftest.py": CONFTEST, "dates.py": SRC_OK,
                          "tests/test_dates.py": TESTS})
    base = git_ops.resolve("HEAD", cwd=repo)
    commit(repo, "tweak", {"tests/test_dates.py": TESTS + "\n\ndef test_friday():\n    assert is_weekend(4) is False\n"})

    witness(repo=repo, base=base, runner_name="pytest", timeout=300)

    untracked = [
        line for line in git_ops.git("status", "--porcelain", cwd=repo).splitlines()
        if "__pycache__" not in line
    ]
    assert untracked == []
