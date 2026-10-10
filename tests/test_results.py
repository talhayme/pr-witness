"""Parsing a runner's report into identified tests."""

from __future__ import annotations

import textwrap

import pytest

from pr_witness.results import Outcome, RunResult, TestCase, parse_junit

PYTEST_XML = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="4" failures="1" skipped="2">
  <testcase classname="tests.test_billing" name="test_ok" time="0.01"/>
  <testcase classname="tests.test_billing" name="test_bad" time="0.02">
    <failure message="assert 1 == 2">E assert 1 == 2</failure>
  </testcase>
  <testcase classname="tests.test_billing" name="test_skipped">
    <skipped type="pytest.skip" message="flaky on CI">reason</skipped>
  </testcase>
  <testcase classname="tests.test_billing" name="test_xfail">
    <skipped type="pytest.xfail" message="known bug">reason</skipped>
  </testcase>
</testsuite></testsuites>
"""

VITEST_XML = """<?xml version="1.0" encoding="UTF-8" ?>
<testsuites name="vitest tests" tests="2">
  <testsuite name="cart.test.ts" tests="2" skipped="1">
    <testcase classname="cart.test.ts" name="subtotal &gt; sums" time="0.1"/>
    <testcase classname="cart.test.ts" name="withTax &gt; applies"><skipped/></testcase>
  </testsuite>
</testsuites>
"""


def write(tmp_path, name, body):
    p = tmp_path / name
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


def test_pytest_identities_are_file_scoped(tmp_path):
    r = parse_junit(write(tmp_path, "p.xml", PYTEST_XML))
    assert set(r.tests) == {
        "tests/test_billing::test_ok",
        "tests/test_billing::test_bad",
        "tests/test_billing::test_skipped",
        "tests/test_billing::test_xfail",
    }


def test_outcomes_are_distinguished(tmp_path):
    r = parse_junit(write(tmp_path, "p.xml", PYTEST_XML))
    assert r.tests["tests/test_billing::test_ok"].outcome is Outcome.PASSED
    assert r.tests["tests/test_billing::test_bad"].outcome is Outcome.FAILED
    assert r.tests["tests/test_billing::test_skipped"].outcome is Outcome.SKIPPED
    # An xfail is an expected failure, not a hidden test: conflating it with
    # a plain skip would flag every known-bug marker in the repository.
    assert r.tests["tests/test_billing::test_xfail"].outcome is Outcome.XFAIL


def test_skip_reason_is_preserved(tmp_path):
    """The reason text is the only thing separating a documented skip from an excuse."""
    r = parse_junit(write(tmp_path, "p.xml", PYTEST_XML))
    assert r.tests["tests/test_billing::test_skipped"].message == "flaky on CI"


def test_ran_excludes_skipped_but_includes_failed(tmp_path):
    r = parse_junit(write(tmp_path, "p.xml", PYTEST_XML))
    assert r.ran == {
        "tests/test_billing::test_ok",
        "tests/test_billing::test_bad",
        "tests/test_billing::test_xfail",
    }
    assert r.counts() == {
        "collected": 4, "ran": 3, "passed": 1, "failed": 1, "skipped": 1,
    }


def test_vitest_identities_keep_the_suite_path(tmp_path):
    """vitest already gives a filename; it must not be mangled into a module path."""
    r = parse_junit(write(tmp_path, "v.xml", VITEST_XML))
    assert set(r.tests) == {
        "cart.test.ts::subtotal > sums",
        "cart.test.ts::withTax > applies",
    }


def test_missing_report_is_an_error_not_an_empty_pass(tmp_path):
    """A run that wrote nothing must never read as a clean suite."""
    r = parse_junit(tmp_path / "absent.xml")
    assert r.collection_error
    assert r.collected == 0


def test_unreadable_report_is_an_error(tmp_path):
    r = parse_junit(write(tmp_path, "bad.xml", "<testsuites>truncated"))
    assert r.collection_error
