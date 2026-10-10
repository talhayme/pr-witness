"""Diff-level integrity: the checkwash bridge and the three JS/TS gaps."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from pr_witness import git_ops, integrity
from pr_witness.compare import Finding, Severity

from .test_git_ops import commit, repo  # noqa: F401


def signals(findings) -> set[str]:
    return {f.signal for f in findings}


def sev(findings, signal) -> Severity:
    return next(f.severity for f in findings if f.signal == signal)


# --- the catch-block scanner -------------------------------------------

@pytest.mark.parametrize("body,expected", [
    ("try { expect(f()).toBe(1); } catch (e) { }", 1),
    ("try { expect(f()).toBe(1); } catch (e) { /* flaky */ }", 1),
    ("try { expect(f()).toBe(1); } catch (e) { console.warn(e); }", 1),
    # A catch that rethrows is not swallowing anything.
    ("try { expect(f()).toBe(1); } catch (e) { throw e; }", 0),
    # The legitimate "this should throw" shape.
    ("try { parse('bad'); } catch (e) { expect(e.message).toMatch(/bad/); }", 0),
    # No assertion inside the try: not our business.
    ("try { setup(); } catch (e) { }", 0),
])
def test_only_assertion_swallowing_catches_are_counted(body, expected):
    assert integrity._count_swallowing_catches(body) == expected


def test_braces_inside_the_try_do_not_confuse_the_scanner():
    source = "try { if (a) { expect(f()).toBe(1); } } catch (e) { }"
    assert integrity._count_swallowing_catches(source) == 1


# --- the three gaps, end to end on a repository -------------------------

BASE_TEST = """import { describe, expect, it } from "vitest";
import { withTax } from "./cart";

describe("withTax", () => {
  it("rounds", () => {
    expect(withTax(10.005, 0.1)).toBe(11.01);
  });
});
"""


def test_a_catch_added_around_an_assertion_is_high(repo):  # noqa: F811
    commit(repo, "init", {"cart.ts": "export const withTax = () => 1;",
                          "cart.test.ts": BASE_TEST})
    base = git_ops.resolve("HEAD", cwd=repo)
    head = commit(repo, "tolerate flakiness", {"cart.test.ts": BASE_TEST.replace(
        "    expect(withTax(10.005, 0.1)).toBe(11.01);",
        "    try {\n      expect(withTax(10.005, 0.1)).toBe(11.01);\n    } catch (e) {\n      // flaky\n    }")})

    findings = integrity.detect_js_gaps(repo, base, head)
    assert "broad_catch" in signals(findings)
    assert sev(findings, "broad_catch") is Severity.HIGH


def test_ts_nocheck_is_higher_than_a_single_ts_ignore(repo):  # noqa: F811
    """One line at the top of a file is not the same as one suppressed line."""
    commit(repo, "init", {"cart.ts": "export const withTax = () => 1;",
                          "cart.test.ts": BASE_TEST})
    base = git_ops.resolve("HEAD", cwd=repo)

    head = commit(repo, "ignore a line", {"cart.test.ts": BASE_TEST.replace(
        "    expect(", "    // @ts-ignore\n    expect(")})
    assert sev(integrity.detect_js_gaps(repo, base, head), "ts_suppression") is Severity.MEDIUM

    head = commit(repo, "nocheck the file", {"cart.test.ts": "// @ts-nocheck\n" + BASE_TEST})
    assert sev(integrity.detect_js_gaps(repo, base, head), "ts_suppression") is Severity.HIGH


def test_only_verification_related_lint_rules_are_reported(repo):  # noqa: F811
    """Disabling no-unused-vars is noise; disabling expect-expect is not."""
    commit(repo, "init", {"cart.ts": "export const withTax = () => 1;",
                          "cart.test.ts": BASE_TEST})
    base = git_ops.resolve("HEAD", cwd=repo)

    head = commit(repo, "cosmetic disable", {
        "cart.test.ts": "/* eslint-disable @typescript-eslint/no-unused-vars */\n" + BASE_TEST})
    assert "lint_suppression" not in signals(integrity.detect_js_gaps(repo, base, head))

    head = commit(repo, "disable expect-expect", {
        "cart.test.ts": "/* eslint-disable vitest/expect-expect */\n" + BASE_TEST})
    assert "lint_suppression" in signals(integrity.detect_js_gaps(repo, base, head))


def test_a_bare_eslint_disable_turns_off_the_verification_rules_too(repo):  # noqa: F811
    """`/* eslint-disable */` with no rule list disables everything."""
    commit(repo, "init", {"cart.ts": "export const withTax = () => 1;",
                          "cart.test.ts": BASE_TEST})
    base = git_ops.resolve("HEAD", cwd=repo)
    head = commit(repo, "disable everything", {
        "cart.test.ts": "/* eslint-disable */\n" + BASE_TEST})
    assert "lint_suppression" in signals(integrity.detect_js_gaps(repo, base, head))


def test_suppressions_outside_test_files_are_ignored(repo):  # noqa: F811
    """Production code may legitimately need a type suppression."""
    commit(repo, "init", {"cart.ts": "export const withTax = () => 1;",
                          "cart.test.ts": BASE_TEST})
    base = git_ops.resolve("HEAD", cwd=repo)
    head = commit(repo, "suppress in source", {
        "cart.ts": "// @ts-ignore\nexport const withTax = () => 1;"})
    assert integrity.detect_js_gaps(repo, base, head) == []


# --- the checkwash bridge -----------------------------------------------

def test_checkwash_is_found_even_when_not_on_path():
    """A virtualenv on sys.path but not PATH must not silently skip the checks."""
    assert integrity.checkwash_command() is not None


def test_checkwash_warnings_do_not_become_our_flags(repo):  # noqa: F811
    """checkwash blocks only on high; mapping its warns to MEDIUM cost 15 points of precision."""
    assert integrity._SEVERITY["warn"] is Severity.LOW
    assert integrity._SEVERITY["high"] is Severity.HIGH


def test_a_documented_skip_downgrades_checkwashs_finding_without_hiding_it(repo):  # noqa: F811
    """We disagree with checkwash here, and the report has to say so."""
    src = "def is_weekend(day):\n    return day >= 5\n"
    test = "from dates import is_weekend\n\n\ndef test_saturday():\n    assert is_weekend(5)\n"
    commit(repo, "init", {"dates.py": src, "tests/test_dates.py": test})
    base = git_ops.resolve("HEAD", cwd=repo)
    head = commit(repo, "skip with a reason", {"tests/test_dates.py":
        "import pytest\n\n" + test.replace(
            "def test_saturday():",
            '@pytest.mark.skip(reason="timezone-dependent, see #501")\ndef test_saturday():')})

    plain, _ = integrity.run_checkwash(repo, base, head)
    assert sev(plain, "checkwash:TEST_DISABLED") is Severity.HIGH

    reconciled, _ = integrity.run_checkwash(
        repo, base, head, documented_skips={"tests/test_dates::test_saturday"})
    f = next(x for x in reconciled if x.signal == "checkwash:TEST_DISABLED")
    assert f.severity is Severity.INFO
    # Still present, and the disagreement is explained rather than hidden.
    assert "checkwash" in f.innocent_explanation


def test_a_static_rewrite_on_a_test_the_run_already_shows_rewritten_stays_at_review():
    run = [Finding("expectation_changed", Severity.MEDIUM, "1 rewritten", tests=["tests/test_a.py::test_x"])]
    cw = [Finding("checkwash:EXPECTED_VALUE_CHANGED", Severity.HIGH, "rewritten", tests=["tests/test_a.py::test_x"]),
          Finding("checkwash:EXPECTED_VALUE_CHANGED", Severity.HIGH, "rewritten", tests=["tests/test_a.py::test_other"])]
    integrity.reconcile_with_run(cw, run)
    assert cw[0].severity is Severity.MEDIUM and "review" in cw[0].innocent_explanation
    # a rewrite the run did not corroborate keeps checkwash's own rating
    assert cw[1].severity is Severity.HIGH


def test_reconcile_is_a_no_op_without_a_run_finding():
    cw = [Finding("checkwash:EXPECTED_VALUE_CHANGED", Severity.HIGH, "rewritten", tests=["t.py::test_x"])]
    integrity.reconcile_with_run(cw, [])
    assert cw[0].severity is Severity.HIGH
