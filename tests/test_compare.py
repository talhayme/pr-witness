"""One test per class of result the comparison can produce.

These are the cases the corpus exercises end to end, reduced to their
essentials so a failure points at the logic rather than at a runner.
"""

from __future__ import annotations

import pytest

from pr_witness.compare import Severity, compare
from pr_witness.results import Outcome, RunResult, TestCase


def run(**outcomes: Outcome | tuple[Outcome, str]) -> RunResult:
    """Build a RunResult from `name=outcome` or `name=(outcome, message)`."""
    r = RunResult()
    for name, value in outcomes.items():
        outcome, message = value if isinstance(value, tuple) else (value, "")
        node = f"tests/test_x::{name}"
        r.tests[node] = TestCase(node, outcome, message)
    return r


def signals(findings) -> set[str]:
    return {f.signal for f in findings}


def by_signal(findings, name):
    return next(f for f in findings if f.signal == name)


P, F, S = Outcome.PASSED, Outcome.FAILED, Outcome.SKIPPED


# --- the cross-run ------------------------------------------------------

def test_base_test_failing_on_head_code_is_the_headline_finding():
    base = run(a=P, b=P)
    head = run(a=P, b=P)
    cross = run(a=P, b=F)
    findings = compare(base, head, cross)
    assert "crossrun" in signals(findings)
    f = by_signal(findings, "crossrun")
    assert f.severity is Severity.HIGH
    assert f.tests == ["tests/test_x::b"]


def test_a_test_already_failing_on_base_is_not_a_regression():
    """Only a behaviour that used to hold and stopped counts."""
    base = run(a=P, b=F)
    head = run(a=P, b=F)
    cross = run(a=P, b=F)
    assert "crossrun" not in signals(compare(base, head, cross))


def test_crossrun_collection_failure_is_reported_softly():
    """An import error after a deliberate removal is expected, not damning."""
    base, head = run(a=P), run(a=P)
    cross = RunResult()
    cross.collection_error = "ModuleNotFoundError: no module named 'removed'"
    f = by_signal(compare(base, head, cross), "crossrun_uncollectable")
    assert f.severity is Severity.LOW
    assert f.innocent_explanation


# --- the denominator ----------------------------------------------------

def test_a_test_collected_but_no_longer_running_is_high():
    base = run(a=P, b=P)
    head = run(a=P, b=(S, ""))
    f = by_signal(compare(base, head, run(a=P, b=P)), "denominator")
    assert f.severity is Severity.HIGH
    assert f.tests == ["tests/test_x::b"]


def test_renaming_tests_is_not_a_finding_when_the_crossrun_confirms_coverage():
    """The commonest honest refactor there is: every identity changes, no coverage does."""
    base = run(old_name=P)
    head = run(new_name=P)
    cross = run(old_name=P)          # base's tests still pass on head's code
    assert signals(compare(base, head, cross)) == set()


def test_removing_tests_is_reported_when_the_crossrun_cannot_confirm_them():
    base = run(a=P, b=P)
    head = run(a=P)
    cross = run(a=P, b=F)            # b's behaviour is gone, not merely renamed
    findings = compare(base, head, cross)
    assert "denominator_removed" in signals(findings)


def test_removal_without_a_crossrun_is_reported_with_a_caveat():
    base, head = run(a=P, b=P), run(a=P)
    f = by_signal(compare(base, head, None), "denominator_removed")
    assert "no cross-run" in f.summary


# --- skips --------------------------------------------------------------

def test_an_undocumented_new_skip_is_high():
    base = run(a=P)
    head = run(a=(S, "flaky"))
    f = by_signal(compare(base, head, run(a=P)), "skip_inflation")
    assert f.severity is Severity.HIGH


@pytest.mark.parametrize("reason", [
    "timezone-dependent, see #501",
    "blocked by https://github.com/x/y/issues/4",
    "waiting on upstream issue in the vendor SDK",
])
def test_a_documented_skip_is_informational_only(reason):
    """A skip that names an issue is a decision, not a cheat."""
    base = run(a=P)
    head = run(a=(S, reason))
    findings = compare(base, head, run(a=P))
    assert signals(findings) == {"skip_documented"}
    assert by_signal(findings, "skip_documented").severity is Severity.INFO


def test_a_documented_skip_is_not_also_reported_as_a_denominator_drop():
    """It stopped running, but it said why. Reporting it twice trains people to ignore us."""
    base = run(a=P)
    head = run(a=(S, "flaky on CI, see #77"))
    assert "denominator" not in signals(compare(base, head, run(a=P)))


# --- clean --------------------------------------------------------------

def test_an_honest_change_produces_nothing():
    base = run(a=P, b=P)
    head = run(a=P, b=P, c=P)        # a test was added, nothing taken away
    assert signals(compare(base, head, run(a=P, b=P))) == set()


def test_head_that_cannot_be_collected_is_high():
    base = run(a=P)
    head = RunResult()
    head.collection_error = "SyntaxError"
    assert by_signal(compare(base, head, None), "head_uncollectable").severity is Severity.HIGH


def test_an_empty_base_is_a_finding_not_a_clean_verdict():
    """Nothing can regress against a base that did not run."""
    base = RunResult(); base.collection_error = "ImportError: cannot import name 'Hashable'"
    findings = compare(base, run(a=P), run(a=P))
    assert "base_uncollectable" in signals(findings)
    assert by_signal(findings, "base_uncollectable").severity is Severity.MEDIUM
