"""Claim extraction and verdicts."""

from __future__ import annotations

import pytest

from pr_witness.claims import Verdict, check, extract, reconcile_with_findings
from pr_witness.compare import Finding, Severity
from pr_witness.results import Outcome, RunResult, TestCase

P, F, S = Outcome.PASSED, Outcome.FAILED, Outcome.SKIPPED


def run(**outcomes) -> RunResult:
    r = RunResult()
    for name, value in outcomes.items():
        outcome, message = value if isinstance(value, tuple) else (value, "")
        node = f"tests/test_x::{name}"
        r.tests[node] = TestCase(node, outcome, message)
    return r


def one(text: str, base, head, cross=None):
    claims = check(extract(text), base, head, cross)
    assert len(claims) == 1, [c.kind for c in claims]
    return claims[0]


# --- extraction ---------------------------------------------------------

@pytest.mark.parametrize("text,kind", [
    ("All 412 tests pass", "count_passed"),
    ("8 passed, 0 failed", "count_passed"),
    ("49/49 passing", "count_passed"),
    ("All tests pass", "all_pass"),
    ("Tests green", "all_pass"),
    ("Suite is green", "all_pass"),
    ("Added 41 tests for the discount logic", "count_added"),
    ("Added `days_until` with 2 tests", "count_added"),
    ("Added test coverage", "added_tests"),
    ("8 tests collected", "count_collected"),
    ("No breaking changes", "no_breaking"),
    ("Fixes #318", "fixes_issue"),
    ("все тесты проходят", "all_pass"),
    ("Добавил 3 теста", "count_added"),
])
def test_claim_shapes_are_recognised(text, kind):
    assert [c.kind for c in extract(text)] == [kind]


@pytest.mark.parametrize("text", [
    "This should be much safer now",
    "Refactored for clarity",
    "Cleaned up the imports",
    "",
])
def test_opinions_are_not_claims(text):
    """A report full of unverifiable sentiment is a report nobody reads."""
    assert extract(text) == []


def test_a_heading_naming_an_issue_is_not_a_claim():
    """`## Fix #318` is a title, not an assertion about a test run."""
    assert extract("## Fix #318\n\nDates now parse.") == []


def test_one_sentence_yields_one_claim_per_distinct_assertion():
    claims = extract("All 3 tests pass, no breaking changes.")
    assert {c.kind for c in claims} == {"count_passed", "no_breaking"}


def test_the_matched_words_are_quoted_not_the_whole_line():
    """Two verdicts on one sentence must each show what they judged."""
    claims = extract("All 3 tests pass, no breaking changes.")
    assert {c.shown for c in claims} == {"3 tests pass", "no breaking changes"}


# --- verdicts -----------------------------------------------------------

def test_a_correct_count_on_a_stable_suite_is_true():
    c = one("2 tests pass", run(a=P, b=P), run(a=P, b=P), run(a=P, b=P))
    assert c.verdict is Verdict.TRUE


def test_a_count_the_run_contradicts_is_false():
    c = one("5 tests pass", run(a=P), run(a=P))
    assert c.verdict is Verdict.FALSE


def test_all_pass_over_a_failing_run_is_false():
    c = one("All tests pass", run(a=P, b=P), run(a=P, b=F))
    assert c.verdict is Verdict.FALSE


def test_a_true_count_over_a_shrunken_denominator_is_misleading():
    """The central trick: narrow the suite, then quote the smaller number."""
    base = run(a=P, b=P, c=P, d=P)
    head = run(a=P, b=P)
    c = one("2 tests pass", base, head, run(a=P, b=P))
    assert c.verdict is Verdict.MISLEADING
    assert "gone" in c.because


def test_the_explanation_names_the_mechanism_not_just_the_symptom():
    """"No longer runs" fits a skip and a deletion; the author needs to know which."""
    base = run(a=P, b=P, c=P)
    head = run(a=P, b=P, c=(S, "flaky"))
    assert "skipped" in one("2 tests pass", base, head, run(a=P, b=P, c=P)).because

    head = run(a=P, b=P)
    assert "gone" in one("2 tests pass", base, head, run(a=P, b=P)).because


def test_green_with_newly_skipped_tests_is_misleading():
    base = run(a=P, b=P)
    head = run(a=P, b=(S, "flaky"))
    c = one("All tests pass", base, head, run(a=P, b=P))
    assert c.verdict is Verdict.MISLEADING
    assert "skipped" in c.because


def test_green_that_the_crossrun_contradicts_is_misleading():
    """Nothing is skipped or missing; only the base branch's tests object."""
    base, head = run(a=P, b=P), run(a=P, b=P)
    c = one("All tests pass", base, head, run(a=P, b=F))
    assert c.verdict is Verdict.MISLEADING
    assert "base branch" in c.because


def test_a_number_from_the_wrong_line_of_the_summary_is_misleading_not_false():
    """Quoting `collected` as `passed` is inaccuracy, not invention."""
    base = run(a=P, b=P, c=P)
    head = run(a=P, b=P, c=(S, "flaky"))
    c = one("3 passed", base, head, run(a=P, b=P, c=P))
    assert c.verdict is Verdict.MISLEADING


def test_but_a_green_number_over_a_red_run_is_false():
    """However it was arrived at, a failing suite described as passing is a lie."""
    base = run(a=P, b=P, c=P)
    head = run(a=P, b=P, c=F)
    c = one("3 tests pass", base, head)
    assert c.verdict is Verdict.FALSE


def test_added_tests_is_checked_against_the_new_test_identities():
    assert one("Added 2 tests", run(a=P), run(a=P, b=P, c=P)).verdict is Verdict.TRUE
    assert one("Added 5 tests", run(a=P), run(a=P, b=P)).verdict is Verdict.FALSE
    assert one("Added test coverage", run(a=P), run(a=P)).verdict is Verdict.FALSE


def test_a_named_subject_with_no_matching_test_is_misleading_not_false():
    """Absence of the name is weak evidence; it may be covered indirectly."""
    c = one("Added tests for parse_date", run(a=P), run(a=P, unrelated=P))
    assert c.verdict is Verdict.MISLEADING


def test_no_breaking_changes_is_decided_by_the_crossrun():
    base, head = run(a=P, b=P), run(a=P, b=P)
    assert one("No breaking changes", base, head, run(a=P, b=P)).verdict is Verdict.TRUE
    assert one("No breaking changes", base, head, run(a=P, b=F)).verdict is Verdict.FALSE


def test_whether_a_fix_is_real_is_honestly_unverifiable():
    """Inventing a heuristic here would be worse than admitting the limit."""
    c = one("Fixes #318", run(a=P), run(a=P))
    assert c.verdict is Verdict.UNVERIFIABLE


# --- reconciliation with the diff ---------------------------------------

def test_a_neutralised_assertion_makes_a_green_claim_misleading():
    """Counts identical on all three runs; only the diff knows."""
    base, head = run(a=P, b=P), run(a=P, b=P)
    claims = check(extract("All tests pass"), base, head, run(a=P, b=P))
    assert claims[0].verdict is Verdict.TRUE

    finding = Finding("broad_catch", Severity.HIGH, "assertion wrapped in try/catch")
    claims = reconcile_with_findings(claims, [finding])
    assert claims[0].verdict is Verdict.MISLEADING
    assert "broad_catch" in claims[0].because


def test_an_unrelated_finding_does_not_taint_a_green_claim():
    """Borrowing every finding would make every claim misleading."""
    base, head = run(a=P, b=P), run(a=P, b=P)
    claims = check(extract("All tests pass"), base, head, run(a=P, b=P))
    finding = Finding("denominator_removed", Severity.MEDIUM, "a test is gone")
    assert reconcile_with_findings(claims, [finding])[0].verdict is Verdict.TRUE


def test_whole_suite_counts_are_unverifiable_when_the_run_was_restricted():
    from pr_witness.claims import Verdict, check, extract
    from pr_witness.results import Outcome, RunResult, TestCase
    head = RunResult()
    head.tests["t::a"] = TestCase("t::a", Outcome.PASSED)
    claims = extract("Test suite: 3128 passed, 0 failed")
    assert check(claims, RunResult(), head, None, restricted=True)[0].verdict is Verdict.UNVERIFIABLE
    assert check(extract("Test suite: 3128 passed, 0 failed"), RunResult(), head, None)[0].verdict is Verdict.FALSE
