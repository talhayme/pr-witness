"""Adapters that make each test runner emit a JUnit XML report.

Every runner here is asked to do the same thing: run the suite and write
JUnit XML somewhere we choose. Nothing else about the runner is modelled,
because the moment the tool starts reasoning about pytest-specific or
jest-specific behaviour it acquires a second job.

Adding a runner means adding its JUnit flag, not writing a new parser.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

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
    # Runners that take test labels rather than file paths translate here;
    # the identity function for everyone else.
    targets: Callable[[list[str]], list[str]] = staticmethod(lambda paths: paths)
    # Extra environment for the run, with {report} substituted — for a
    # runner whose JUnit output is configured out of band.
    env: dict[str, str] = field(default_factory=dict)
    # Files the runner needs beside the report (a settings module, say).
    # Written into the report's directory, never into the tree under test.
    prepare: Callable[[Path], None] = staticmethod(lambda report: None)

    def build(self, report: Path, paths: list[str] | None = None) -> list[str]:
        argv = shlex.split(self.command.replace("{report}", str(report)))
        return argv + list(self.targets(list(paths or [])))

    def environment(self, report: Path, base: dict[str, str] | None) -> dict[str, str] | None:
        if not self.env:
            return base
        env = dict(base if base is not None else os.environ)
        for key, value in self.env.items():
            value = value.replace("{report}", str(report)).replace("{report_dir}", str(report.parent))
            if key == "PYTHONPATH":
                value = os.pathsep.join(p for p in (value, env.get("PYTHONPATH", "")) if p)
            env[key] = value
        return env


# Django's own test suite runs through tests/runtests.py, which takes test
# labels (`migrations.test_writer`), not paths, and writes no JUnit of its
# own. unittest-xml-reporting's Django runner does; it is selected through a
# settings module that wraps the suite's own `test_sqlite` and is written
# next to the report, so the tree under test is left untouched.
_DJANGO_SETTINGS = """\
# Written by pr-witness for one run; see pr_witness/runners.py.
import os
from test_sqlite import *  # noqa: F401,F403  (tests/ is on sys.path under runtests.py)

TEST_RUNNER = "xmlrunner.extra.djangotestrunner.XMLTestRunner"
TEST_OUTPUT_DIR = os.path.dirname(os.environ["PR_WITNESS_REPORT"])
TEST_OUTPUT_FILE_NAME = os.path.basename(os.environ["PR_WITNESS_REPORT"])
TEST_OUTPUT_VERBOSE = 0
"""


def _django_labels(paths: list[str]) -> list[str]:
    """`tests/migrations/test_writer.py` → `migrations.test_writer`."""
    labels = []
    for p in paths:
        p = p[6:] if p.startswith("tests/") else p
        p = p[:-3] if p.endswith(".py") else p
        if p.endswith("/__init__"):
            p = p[: -len("/__init__")]
        labels.append(p.replace("/", "."))
    return labels


def _django_prepare(report: Path) -> None:
    report.parent.mkdir(parents=True, exist_ok=True)
    (report.parent / "pr_witness_django_settings.py").write_text(_DJANGO_SETTINGS, encoding="utf-8")


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
    # bun's test runner writes JUnit itself; paths are passed as filters.
    "bun": Runner(
        "bun",
        "bun test --reporter=junit --reporter-outfile={report}",
    ),
    "django": Runner(
        "django",
        "python tests/runtests.py --settings=pr_witness_django_settings --parallel=1 --noinput -v1",
        targets=_django_labels,
        env={"PYTHONPATH": "{report_dir}", "PR_WITNESS_REPORT": "{report}"},
        prepare=_django_prepare,
    ),
}


def detect(root: Path) -> str | None:
    """Guess the runner from what the repository contains.

    A guess, explicitly: `--runner` overrides it, and the report says which
    runner was used so a wrong guess is visible rather than silent.
    """
    if (root / "go.mod").exists():
        return "go"
    if (root / "tests" / "runtests.py").exists() and (root / "django").is_dir():
        return "django"

    pkg = root / "package.json"
    if pkg.exists():
        text = pkg.read_text(encoding="utf-8", errors="replace")
        if '"bun test' in text or (root / "bun.lock").exists() or (root / "bun.lockb").exists():
            return "bun"
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

    runner.prepare(report)
    argv = runner.build(report, paths)
    try:
        proc = subprocess.run(
            argv, cwd=cwd, capture_output=True, text=True, timeout=timeout,
            env=runner.environment(report, env),
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
