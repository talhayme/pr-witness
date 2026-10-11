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


# --- which file a test lives in -------------------------------------------

def test_a_class_based_test_counts_as_touched_when_its_file_changed():
    from pr_witness.compare import _touched
    changed = {"tests/test_x.py", "tests/migrations/test_writer.py"}
    assert _touched("tests/test_x/TestDates::test_monday", changed)
    assert _touched("migrations/test_writer/WriterTests::test_serialize", changed)   # runner run from tests/
    assert _touched("tests/test_x::test_plain", changed)
    assert not _touched("tests/test_y/TestOther::test_q", changed)


def test_a_base_where_every_test_fails_is_no_evidence_not_clean():
    base = run(a=(F, "ModuleNotFoundError: No module named 'pandas'"), b=(F, "ModuleNotFoundError: No module named 'pandas'"))
    head = run(a=F, b=F)
    f = compare(base, head, head)
    assert "base_broken" in signals(f)
    assert "pandas" in by_signal(f, "base_broken").summary


def test_a_base_with_some_failures_is_reported_as_context():
    base = run(a=P, b=(F, "AssertionError"))
    head = run(a=P, b=P)
    f = compare(base, head, run(a=P, b=F))
    assert "base_not_green" in signals(f) and by_signal(f, "base_not_green").severity is Severity.INFO
    assert "base_broken" not in signals(f)


# --- deleted tests ------------------------------------------------------------

def test_a_deleted_test_that_still_passes_on_the_new_code_is_surfaced():
    base = run(keep=P, gone=P)
    head = run(keep=P)
    cross = run(keep=P, gone=P)                       # the old test still passes: behaviour kept, coverage gone
    f = compare(base, head, cross, changed_test_files={"tests/test_x.py"})
    assert by_signal(f, "tests_removed_still_passing").tests == ["tests/test_x::gone"]


def test_a_test_folded_into_a_parametrised_sibling_is_not_a_deletion():
    base = run(test_discount_half=P, test_discount_zero=P)
    head = RunResult()
    for node in ("tests/test_x::test_discount[50]", "tests/test_x::test_discount[0]"):
        head.tests[node] = TestCase(node, P)
    cross = run(test_discount_half=P, test_discount_zero=P)
    f = compare(base, head, cross, changed_test_files={"tests/test_x.py"})
    assert "tests_removed_still_passing" not in signals(f)


def test_a_rewritten_test_that_fails_because_its_subject_is_gone_is_cleanup_not_review():
    base = run(a=P, uses_removed_fn=P)
    head = run(a=P)
    cross = run(a=P, uses_removed_fn=(F, "TypeError: classifyAttachmentType is not a function"))
    f = compare(base, head, cross, changed_test_files={"tests/test_x.py"})
    assert "tests_removed_subject_gone" in signals(f) and "expectation_changed" not in signals(f)


# --- red on base, green now ---------------------------------------------------

def test_a_red_test_made_green_by_editing_the_test_is_surfaced():
    base = run(a=P, red=(F, "AssertionError: 'commit' not in stages"))
    head = run(a=P, red=P)
    cross = run(a=P, red=(F, "AssertionError: 'commit' not in stages"))   # old test still fails on the new code
    f = compare(base, head, cross, changed_test_files={"tests/test_x.py"})
    assert by_signal(f, "greened_by_test_edit").tests == ["tests/test_x::red"]


def test_a_red_test_fixed_by_the_code_is_not_surfaced():
    base = run(a=P, red=F)
    head = run(a=P, red=P)
    cross = run(a=P, red=P)                                                # old test passes on the new code: the code fixed it
    f = compare(base, head, cross, changed_test_files={"tests/test_x.py"})
    assert "greened_by_test_edit" not in signals(f)


def test_a_skip_for_an_external_cause_counts_as_documented():
    from pr_witness.compare import _skip_is_documented
    assert _skip_is_documented("pre-commit hooks not installed (run: uv run pre-commit install)")
    assert not _skip_is_documented("flaky")


# --- skipped tests that are new ---------------------------------------------

def test_a_skipped_test_the_pull_request_added_is_not_skip_inflation():
    """optimize-anything: three new integration tests behind skipif were a flag."""
    base = run(a=P)
    head = run(a=P, new_integration=(S, "nope"))
    f = compare(base, head, run(a=P))
    assert "skip_inflation" not in signals(f)
    assert by_signal(f, "added_tests_skipped").severity is Severity.LOW


def test_an_existing_test_newly_skipped_is_still_skip_inflation():
    base = run(a=P, b=P)
    head = run(a=P, b=(S, "nope"))
    f = compare(base, head, run(a=P, b=P))
    assert by_signal(f, "skip_inflation").tests == ["tests/test_x::b"]
    assert "added_tests_skipped" not in signals(f)


def test_a_reason_that_says_something_is_required_is_an_external_cause():
    from pr_witness.compare import _skip_is_documented
    assert _skip_is_documented("OPENAI_API_KEY required")
    assert _skip_is_documented("requires a running testnet")
