"""Adapters that make each test runner emit a JUnit XML report.

Every runner here is asked to do the same thing: run the suite and write
JUnit XML somewhere we choose. Nothing else about the runner is modelled,
because the moment the tool starts reasoning about pytest-specific or
jest-specific behaviour it acquires a second job.

Adding a runner means adding its JUnit flag, not writing a new parser.
"""

from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

from pr_witness.results import RunResult, parse_junit

# Exit codes that mean "the suite ran and some tests failed" rather than
# "the runner could not start". Anything else is treated as a broken run,
# because a failure to launch must never be read as a clean suite.
_RAN_WITH_FAILURES = {0, 1}


@dataclass(frozen=True)
class Runner:
    name: str
    # {report} is substituted with the path the report must be written to.
    command: str
    # pytest exits 5 on "no tests collected", which is a real answer, not a
    # crash: a PR that collects nothing is exactly what we want to report.
    ok_exit_codes: frozenset[int] = frozenset(_RAN_WITH_FAILURES)

    def build(self, report: Path, paths: list[str] | None = None) -> list[str]:
        argv = shlex.split(self.command.replace("{report}", str(report)))
        return argv + list(paths or [])


RUNNERS: dict[str, Runner] = {
    "pytest": Runner(
        "pytest",
        "pytest -p no:cacheprovider -q --junit-xml={report}",
        frozenset({0, 1, 5}),
    ),
    "vitest": Runner(
        "vitest",
        "npx vitest run --reporter=junit --outputFile={report}",
    ),
    "jest": Runner(
        "jest",
        "npx jest --ci --reporters=jest-junit",
    ),
    "go": Runner(
        "go",
        "go test ./... -v",
    ),
}


def detect(root: Path) -> str | None:
    """Guess the runner from what the repository contains.

    A guess, explicitly: `--runner` overrides it, and the report says which
    runner was used so a wrong guess is visible rather than silent.
    """
    if (root / "go.mod").exists():
        return "go"

    pkg = root / "package.json"
    if pkg.exists():
        text = pkg.read_text(encoding="utf-8", errors="replace")
        if "vitest" in text:
            return "vitest"
        if "jest" in text:
            return "jest"

    if any((root / f).exists() for f in ("pytest.ini", "setup.cfg", "tox.ini")):
        return "pytest"
    if (root / "pyproject.toml").exists():
        return "pytest"
    if list(root.glob("test_*.py")) or list(root.glob("tests/**/*.py")):
        return "pytest"
    return None


def run(
    runner: Runner,
    cwd: Path,
    report: Path,
    paths: list[str] | None = None,
    timeout: int = 1800,
    env: dict[str, str] | None = None,
) -> RunResult:
    """Run the suite and read back what it reported."""
    report.parent.mkdir(parents=True, exist_ok=True)
    if report.exists():
        report.unlink()

    argv = runner.build(report, paths)
    try:
        proc = subprocess.run(
            argv, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env,
        )
    except FileNotFoundError:
        result = RunResult()
        result.collection_error = f"{runner.name} not found: {' '.join(argv)}"
        result.exit_code = 127
        return result
    except subprocess.TimeoutExpired:
        result = RunResult()
        result.collection_error = f"{runner.name} timed out after {timeout}s"
        result.exit_code = 124
        return result

    result = parse_junit(report)
    result.exit_code = proc.returncode

    # A runner that died without writing a report tells us nothing, and
    # "nothing" must not be mistaken for "no failures". Keep its own words:
    # a missing dependency or a syntax error is usually in that output.
    if proc.returncode not in runner.ok_exit_codes and not result.tests:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-20:]
        result.collection_error = (
            f"{runner.name} exited {proc.returncode} without reporting any test\n"
            + "\n".join(tail)
        )

    return result
