"""The Claude Code hooks, fed the JSON they would receive from the editor."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parent.parent / "claude-plugin" / "scripts"


def run_hook(script: str, event: dict, env: dict | None = None) -> dict | None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / script)],
        input=json.dumps(event), capture_output=True, text=True,
        env={**os.environ, **(env or {})}, timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout) if proc.stdout.strip() else None


def decision(out):
    return out["hookSpecificOutput"]["permissionDecision"] if out else None


# --- guard_tests.py -----------------------------------------------------

@pytest.mark.parametrize("path", [
    "tests/test_billing.py", "src/pkg/test_x.py", "src/cart.test.ts",
    "conftest.py", "pytest.ini", ".github/workflows/ci.yml",
])
def test_editing_a_test_file_asks(path):
    out = run_hook("guard_tests.py", {"tool_name": "Edit", "tool_input": {"file_path": path}})
    assert decision(out) == "ask"
    assert path in out["hookSpecificOutput"]["permissionDecisionReason"]


@pytest.mark.parametrize("path", ["src/billing.py", "README.md", "src/cart.ts"])
def test_editing_production_code_is_silent(path):
    assert run_hook("guard_tests.py", {"tool_name": "Edit", "tool_input": {"file_path": path}}) is None


def test_deleting_a_test_via_bash_asks():
    out = run_hook("guard_tests.py", {"tool_name": "Bash",
                                      "tool_input": {"command": "rm tests/test_billing.py"}})
    assert decision(out) == "ask"


def test_an_ordinary_bash_command_is_silent():
    assert run_hook("guard_tests.py", {"tool_name": "Bash", "tool_input": {"command": "pytest -q"}}) is None


def test_deny_mode_denies_and_off_mode_is_silent():
    event = {"tool_name": "Write", "tool_input": {"file_path": "tests/test_a.py"}}
    assert decision(run_hook("guard_tests.py", event, {"PR_WITNESS_GUARD": "deny"})) == "deny"
    assert run_hook("guard_tests.py", event, {"PR_WITNESS_GUARD": "off"}) is None


def test_malformed_input_never_breaks_the_tool_call():
    proc = subprocess.run([sys.executable, str(SCRIPTS / "guard_tests.py")],
                          input="not json", capture_output=True, text=True)
    assert proc.returncode == 0 and not proc.stdout.strip()


# --- check_claims.py ----------------------------------------------------

def test_a_message_without_a_claim_does_nothing(tmp_path):
    out = run_hook("check_claims.py", {"last_assistant_message": "Refactored the parser.",
                                       "cwd": str(tmp_path)})
    assert out is None


def test_a_claim_without_pr_witness_installed_says_so(tmp_path):
    out = run_hook("check_claims.py",
                   {"last_assistant_message": "All 12 tests pass.", "cwd": str(tmp_path)},
                   {"PATH": "/nonexistent"})
    assert "not installed" in out["hookSpecificOutput"]["additionalContext"]


def test_a_false_claim_is_reported_in_the_session(tmp_path):
    """End to end: a repo where the message lies, pr-witness on PATH."""
    from .test_git_ops import commit
    repo = tmp_path / "repo"; repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    conftest = "import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).parent))\n"
    commit(repo, "base", {"conftest.py": conftest, "m.py": "def f(): return 1\n",
                          "tests/test_m.py": "from m import f\n\ndef test_f():\n    assert f() == 1\n"})
    subprocess.run(["git", "branch", "origin-main-stand-in"], cwd=repo)
    commit(repo, "head", {"m.py": "def f(): return 2\n"})   # breaks the test, leaves it alone

    venv_bin = str(Path(sys.executable).parent)
    out = run_hook("check_claims.py",
                   {"last_assistant_message": "Done. All 5 tests pass.", "cwd": str(repo)},
                   {"PATH": venv_bin + os.pathsep + os.environ["PATH"],
                    "PR_WITNESS_BASE": "origin-main-stand-in"})
    text = out["hookSpecificOutput"]["additionalContext"]
    assert "5 tests pass" in text
    assert "✗" in text
