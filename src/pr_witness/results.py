"""The result of one test run, as a set of identified tests.

Phase 0 taught the lesson this module exists for: counting is not enough.
`describe.only` in vitest leaves the collected count untouched and moves
three tests into `skipped`; narrowing `testpaths` in pytest shrinks the count
outright. Same trick, two different numbers.

So a run is represented as a mapping from a stable test identity to its
outcome, and every question the tool asks — did the denominator shrink, did
skips climb, did a base test start failing — is answered by comparing sets,
not totals.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Outcome(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"
    XFAIL = "xfail"

    @property
    def ran(self) -> bool:
        """Did this test actually exercise the code?

        A skipped test is collected but proves nothing, which is the whole
        point of the skip-inflation trick.
        """
        return self in (Outcome.PASSED, Outcome.FAILED, Outcome.ERROR, Outcome.XFAIL)

    @property
    def broken(self) -> bool:
        return self in (Outcome.FAILED, Outcome.ERROR)


@dataclass(frozen=True)
class TestCase:
    """One test, identified the way a human would point at it.

    `id` is `file::suite::name` — stable across a run on either branch, and
    comparable between them. It deliberately excludes timing, hostnames and
    line numbers, which change for reasons that are not the tool's business.
    """

    # pytest collects any class named Test*; this is a data record, not a
    # suite, and without this it warns in every project that imports us.
    __test__ = False

    id: str
    outcome: Outcome
    message: str = ""
    duration: float = 0.0

    @property
    def file(self) -> str:
        return self.id.split("::", 1)[0]


@dataclass
class RunResult:
    """Every test a runner reported, plus how the run itself went."""

    tests: dict[str, TestCase] = field(default_factory=dict)
    exit_code: int = 0
    # A run that crashed before collecting anything is not a run with zero
    # failures; conflating them would let a broken import look like success.
    collection_error: str = ""

    @property
    def collected(self) -> int:
        return len(self.tests)

    @property
    def ran(self) -> set[str]:
        return {t.id for t in self.tests.values() if t.outcome.ran}

    @property
    def passed(self) -> set[str]:
        return {t.id for t in self.tests.values() if t.outcome is Outcome.PASSED}

    @property
    def failed(self) -> set[str]:
        return {t.id for t in self.tests.values() if t.outcome.broken}

    @property
    def skipped(self) -> set[str]:
        return {t.id for t in self.tests.values() if t.outcome is Outcome.SKIPPED}

    def counts(self) -> dict[str, int]:
        return {
            "collected": self.collected,
            "ran": len(self.ran),
            "passed": len(self.passed),
            "failed": len(self.failed),
            "skipped": len(self.skipped),
        }


def _node_id(classname: str, name: str) -> str:
    """Build one identity out of a JUnit testcase's two halves.

    pytest writes `tests.test_billing` / `test_discount_half`; vitest writes
    `cart.test.ts` / `subtotal > sums price times quantity`. Normalising both
    to `file::name` lets a Python and a TypeScript case go through the same
    comparison code.
    """
    cls = (classname or "").strip()
    nm = (name or "").strip()
    if not cls:
        return nm
    # pytest dots a module path; vitest already gives a filename.
    if "/" not in cls and "\\" not in cls and not cls.endswith((".ts", ".js", ".tsx", ".jsx")):
        cls = cls.replace(".", "/")
    return f"{cls}::{nm}"


def parse_junit(path: Path | str) -> RunResult:
    """Read a JUnit XML report into a RunResult.

    JUnit XML is the one format pytest, jest, vitest and go-junit-report all
    speak, which is why the plan picked it: supporting a new runner means
    finding its JUnit flag, not writing a new parser.
    """
    path = Path(path)
    result = RunResult()
    if not path.exists():
        result.collection_error = f"no report written at {path}"
        return result

    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        result.collection_error = f"unreadable report: {exc}"
        return result

    suites = root.iter("testsuite") if root.tag == "testsuites" else [root]
    for suite in suites:
        for case in suite.iter("testcase"):
            node = _node_id(case.get("classname", ""), case.get("name", ""))
            outcome, message = Outcome.PASSED, ""

            # A testcase carries at most one of these children. Order matters:
            # an errored test is not a failing one, and pytest reports an
            # xfail as a skipped element with a distinguishing type.
            if (el := case.find("error")) is not None:
                outcome = Outcome.ERROR
                message = el.get("message", "") or (el.text or "").strip()
            elif (el := case.find("failure")) is not None:
                outcome = Outcome.FAILED
                message = el.get("message", "") or (el.text or "").strip()
            elif (el := case.find("skipped")) is not None:
                kind = el.get("type", "")
                outcome = Outcome.XFAIL if "xfail" in kind.lower() else Outcome.SKIPPED
                message = el.get("message", "") or (el.text or "").strip()

            try:
                duration = float(case.get("time", "0") or 0)
            except ValueError:
                duration = 0.0

            result.tests[node] = TestCase(node, outcome, message, duration)

    return result
