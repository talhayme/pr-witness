"""Compare three runs and say what the pull request did to the test suite.

The three runs, and why each exists:

    base    base tests on base code   what the suite claimed before
    head    head tests on head code   what CI reports on the pull request
    cross   base tests on head code   the combination nobody runs

The cross-run is the point. CI only ever runs new tests against new code, so
a change that breaks a behaviour and edits the test that guarded it is green
twice over. Running the old tests against the new code asks the question CI
cannot: did a behaviour that used to hold stop holding?
"""

from __future__ import annotations

import re

from dataclasses import dataclass, field
from enum import Enum

from pr_witness.results import Outcome, RunResult


class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class Finding:
    signal: str
    severity: Severity
    summary: str
    # Why this might be innocent. Every finding carries one, because the
    # plan's first principle is "do no harm" and a flag without an escape
    # route is an accusation.
    innocent_explanation: str = ""
    tests: list[str] = field(default_factory=list)
    diff: str = ""      # old vs new assertion, when the finding is about a rewrite

    def as_dict(self) -> dict:
        d = {
            "signal": self.signal,
            "severity": self.severity.value,
            "summary": self.summary,
            "innocent_explanation": self.innocent_explanation,
            "tests": sorted(self.tests),
        }
        if self.diff:
            d["diff"] = self.diff
        return d


# A skip whose reason names a tracking issue or an external cause is the
# documented kind. Phase 0 found that counts alone cannot separate a
# legitimate flaky-test skip from an excuse, and this is the cheapest
# separator that does not need a model.
_ISSUE_MARKERS = ("#", "http://", "https://", "issue", "ticket", "jira", "bug ")
# An external cause: something the test needs that this machine does not
# have. "pre-commit hooks not installed", "requires CANFAR runtime", "no
# network". Still a skip a reviewer should see in the count — but not an
# excuse, and the first real cases were full of them.
_EXTERNAL_MARKERS = ("not installed", "not present", "not available", "unavailable", "missing", "requires",
                     "needs ", "no network", "offline", "not found", "not configured", "not set", "only on ",
                     "unsupported on", "skipped on", "ci only", "not supported")


def _skip_is_documented(message: str) -> bool:
    text = (message or "").strip().lower()
    if len(text) < 8:
        return False
    return any(marker in text for marker in _ISSUE_MARKERS) or any(marker in text for marker in _EXTERNAL_MARKERS)


def _test_file_of(node_id: str) -> str:
    """`tests/test_dates::test_monday` → `tests/test_dates`; `cart.test.ts::x` → `cart.test.ts`."""
    return node_id.split("::", 1)[0]


def _fn_name(node_id: str) -> str:
    """`tests/test_x/TestA::test_m[1]` → `test_m`; `file.test.ts::suite::does x` → `does x`."""
    return node_id.rsplit("::", 1)[-1].split("[", 1)[0]


# A failure that says "the thing this test used no longer exists" — an
# import or a name, not an assertion. The old test did not start asserting
# something different; its subject was removed. Cleanup, until the diff says
# otherwise.
_GONE = re.compile(r"ImportError|ModuleNotFoundError|cannot import name|is not a function|is not defined"
                   r"|has no attribute|NameError|ReferenceError|Cannot find module|is not a constructor"
                   r"|AttributeError: module", re.I)


def _subject_gone(message: str) -> bool:
    return bool(message) and bool(_GONE.search(message))


def _merged_into(node_id: str, head_tests) -> bool:
    """Was this test folded into a parametrised or renamed sibling in the same file?

    `test_discount_half` → `test_discount[50-0.5]`: the new name is a prefix
    of the old one (or the reverse), in the same file. The run cannot tell a
    consolidation from a deletion otherwise; this is the cheapest honest
    tie-breaker, and it is named here so it can be argued with.
    """
    file_part = _test_file_of(node_id)
    name = _fn_name(node_id)
    for other in head_tests:
        if _test_file_of(other) != file_part:
            continue
        o = _fn_name(other)
        if o != name and len(o) >= 6 and (name.startswith(o) or o.startswith(name)):
            return True
    return False


def _touched(node_id: str, changed_test_files: set[str]) -> bool:
    """Did the pull request edit, rename or delete the file this test lives in?

    The file half of a node id may carry a class (`tests/test_x/TestA`) and,
    for a runner invoked from a subdirectory, may lack a leading directory
    (`migrations/test_writer/WriterTests` for `tests/migrations/test_writer.py`).
    So every prefix of it is tried against the changed path and its stem.
    """
    f = _test_file_of(node_id)
    parts = f.split("/")
    candidates = ["/".join(parts[:i]) for i in range(len(parts), 0, -1)]
    for path in changed_test_files:
        stem = path[:-3] if path.endswith(".py") else path
        for cand in candidates:
            if cand in (path, stem) or path.endswith("/" + cand) or stem.endswith("/" + cand):
                return True
    return False


def compare(base: RunResult, head: RunResult, cross: RunResult | None = None,
            changed_test_files: set[str] | None = None,
            assertion_diffs: dict[str, str] | None = None) -> list[Finding]:
    """Produce every finding the three runs support.

    Findings are evidence, not verdicts. The caller decides what to do with
    them; by default pr-witness reports and blocks nothing.

    `changed_test_files` is the set of test files the pull request touched.
    It decides the one distinction the run itself cannot make: a base test
    failing on the new code is a hidden regression if the PR never touched
    that test, and an *expectation change* if the PR rewrote it. The first
    is a flag; the second is for a human to review — honest and dishonest
    rewrites look identical to the run (see corpus/real/swebench).
    """
    findings: list[Finding] = []
    changed_test_files = changed_test_files or set()
    assertion_diffs = assertion_diffs or {}

    # ---- a base that did not run proves nothing -----------------------------
    # With no base results every comparison below is vacuous: no base test
    # can be seen to fail, no denominator can shrink. A clean verdict on an
    # empty base would be the tool lying by omission.
    if base.collection_error or (base.collected == 0 and not base.collection_error):
        findings.append(Finding(
            "base_uncollectable",
            Severity.MEDIUM,
            "the base branch's tests could not be collected, so nothing below is evidence: "
            + (base.collection_error.splitlines()[0] if base.collection_error else "0 tests collected"),
            "Usually the environment, not the change: a Python version the base "
            "commit predates, a missing dependency, or the wrong --paths.",
        ))

    # A base that collects but passes nothing is an environment that is not
    # reproducing the suite (a missing import in conftest fails every test
    # the same way). The comparison is then vacuous: the same failure on both
    # sides is not a clean verdict, it is no evidence.
    if base.tests and not base.passed and all(t.outcome.broken for t in base.tests.values()):
        first = next(iter(base.tests.values()))
        findings.append(Finding(
            "base_broken",
            Severity.MEDIUM,
            f"every one of the base branch's {len(base.tests)} tests failed or errored, so nothing below is evidence: "
            + (first.message.strip().splitlines()[-1][:160] if first.message else "no message"),
            "Almost always the environment, not the change: a dependency the "
            "project imports but does not declare, a service the tests expect.",
        ))

    # A base that is not green is context every reader needs: the cross-run
    # can only speak for tests that passed on the base branch, and a change
    # that turns 51 red tests green deserves a different kind of look than
    # one that touches a green suite.
    base_failing = sorted(n for n, tc in base.tests.items() if tc.outcome.broken)
    if base_failing and base.passed:
        findings.append(Finding(
            "base_not_green",
            Severity.INFO,
            f"{len(base_failing)} of {len(base.tests)} base-branch tests already fail on the base branch; "
            "the cross-run says nothing about them",
            "Common: tests written ahead of the implementation, or an environment "
            "the suite expects. Worth knowing when the pull request makes them pass.",
            base_failing[:50],
        ))

    # ---- the cross-run ---------------------------------------------------
    if cross is not None:
        if cross.collection_error:
            findings.append(Finding(
                "crossrun_uncollectable",
                Severity.LOW,
                "the base branch's tests could not be collected against this code: "
                + cross.collection_error.splitlines()[0],
                "Expected when the pull request deliberately removes or renames "
                "something the old tests import. Compare against what the change "
                "set out to do.",
            ))
        else:
            # A test that passed on base and fails on head. This is the one
            # finding the whole tool exists for.
            regressed = sorted(t for t in base.passed & cross.failed)
            untouched = [t for t in regressed if not _touched(t, changed_test_files)]
            rewritten = [t for t in regressed if _touched(t, changed_test_files)]
            if untouched:
                findings.append(Finding(
                    "crossrun",
                    Severity.HIGH,
                    f"{len(untouched)} test(s) the pull request did not touch pass on "
                    "the base branch and fail against this code — a regression the "
                    "pull request's own tests do not show",
                    "Legitimate only if the behaviour change is intended and the "
                    "test was simply forgotten; then update it and say so.",
                    untouched,
                ))
            gone_subject = [t for t in rewritten if _subject_gone(cross.tests[t].message)]
            rewritten = [t for t in rewritten if t not in gone_subject]
            if gone_subject:
                findings.append(Finding(
                    "tests_removed_subject_gone",
                    Severity.LOW,
                    f"{len(gone_subject)} test(s) the pull request rewrote or removed fail against this code "
                    "because what they used no longer exists (an import or a name, not an assertion)",
                    "What cleanup looks like: the code went, its tests went. Worth a glance "
                    "that nothing else depended on it.",
                    gone_subject,
                ))
            if rewritten:
                detail = ""
                shown = [assertion_diffs[t] for t in rewritten if t in assertion_diffs]
                if shown:
                    detail = "\n".join(shown[:3])
                findings.append(Finding(
                    "expectation_changed",
                    Severity.MEDIUM,
                    f"{len(rewritten)} test(s) the pull request rewrote assert something "
                    "different now: the base version fails against this code",
                    "Exactly what a change of specification looks like — and exactly "
                    "what a test edited to match a bug looks like. The run cannot "
                    "tell them apart; the old and new assertion are shown so a "
                    "reviewer can.",
                    rewritten,
                ))
                if detail:
                    findings[-1].diff = detail

            # The cross-run's blind spot, closed: a test that was red on the
            # base branch and is green now. If its *old* version still fails
            # against the new code, the code change did not fix it — the
            # test edit did. Loosened assertion, swapped expected value, or a
            # fair rewrite after a behaviour change: the run cannot say
            # which, so it shows the test and a human reads the diff.
            greened = sorted(
                t for t in base.failed & head.passed
                if t in cross.failed and _touched(t, changed_test_files)
            )
            if greened:
                findings.append(Finding(
                    "greened_by_test_edit",
                    Severity.MEDIUM,
                    f"{len(greened)} test(s) failed on the base branch and pass now, but their old version "
                    "still fails against this code: the test edit made them pass, not the code change",
                    "Fair when the test encoded the old behaviour and the change was intended; "
                    "also exactly how a failing suite is made green without fixing anything.",
                    greened,
                ))

            # A base test that no longer even runs on the new code. Softer
            # than a failure, but it is how a removed guard disappears.
            vanished = sorted(base.ran - cross.tests.keys())
            if vanished:
                findings.append(Finding(
                    "crossrun_vanished",
                    Severity.MEDIUM,
                    f"{len(vanished)} test(s) from the base branch no longer "
                    "exist when collected against this code",
                    "Normal if those tests covered code this pull request "
                    "removed.",
                    vanished,
                ))
            # A test the PR deleted that still passes against the PR's code:
            # the behaviour is there and nothing verifies it any more. Not
            # cleanup — cleanup makes the old test fail or vanish, because
            # what it called is gone. A test that merely moved (same name
            # under another id) is not deleted.
            head_names = {_fn_name(n) for n in head.tests}
            deleted = [n for n in sorted(base.ran) if n not in head.tests and _touched(n, changed_test_files)
                       and _fn_name(n) not in head_names and not _merged_into(n, head.tests)]
            still_passing = [n for n in deleted if n in cross.passed]
            if still_passing:
                findings.append(Finding(
                    "tests_removed_still_passing",
                    Severity.MEDIUM,
                    f"{len(still_passing)} test(s) the pull request deleted still pass against its code: "
                    "the behaviour they verified is still there, and nothing verifies it now",
                    "Legitimate when the behaviour is covered elsewhere or the test was "
                    "wrong; either way the coverage is gone and a reviewer should know.",
                    still_passing,
                ))

    # ---- the denominator -------------------------------------------------
    # Compared as sets of identities, not as totals. Phase 0: `describe.only`
    # leaves vitest's collected count unchanged and moves tests to skipped,
    # while pytest's testpaths narrowing shrinks the count. Only the set of
    # tests that actually *ran* behaves the same way in both.
    stopped = sorted(base.ran - head.ran)
    if stopped:
        still_present = [t for t in stopped if t in head.tests]
        gone = [t for t in stopped if t not in head.tests]

        # A documented skip is reported below as `skip_documented`, at INFO.
        # Without this, every explained skip would also be a HIGH finding
        # here, which is the fastest way to teach people to ignore the tool.
        undocumented_stop = [
            t for t in still_present
            if not (
                head.tests[t].outcome is Outcome.SKIPPED
                and _skip_is_documented(head.tests[t].message)
            )
        ]
        if undocumented_stop:
            findings.append(Finding(
                "denominator",
                Severity.HIGH,
                f"{len(undocumented_stop)} test(s) are still collected but no "
                "longer run",
                "A test can be legitimately skipped — but a skip that is not "
                "explained reads as one that was hidden.",
                undocumented_stop,
            ))

        # A test identity disappearing is not evidence of anything on its
        # own. Renaming a file, splitting a module and collapsing cases into
        # a parametrised one all delete every identity they touch while
        # changing no coverage at all — and those are among the commonest
        # honest refactors there are.
        #
        # The cross-run settles it. If the behaviour really is still covered,
        # the base branch's own tests still pass against the new code. So an
        # identity that vanished is only worth reporting when the cross-run
        # could not confirm it, which `crossrun` and `crossrun_vanished`
        # already report with better evidence.
        if gone and cross is not None and not cross.collection_error:
            unconfirmed = sorted(set(gone) - cross.passed)
            if unconfirmed:
                findings.append(Finding(
                    "denominator_removed",
                    Severity.MEDIUM,
                    f"{len(unconfirmed)} test(s) that ran on the base branch "
                    "are gone, and the behaviour they covered is no longer "
                    "verified",
                    "Expected when the feature they covered was removed. "
                    "Check whether the code they exercised went away too.",
                    unconfirmed,
                ))
        elif gone:
            findings.append(Finding(
                "denominator_removed",
                Severity.MEDIUM,
                f"{len(gone)} test(s) that ran on the base branch are gone "
                "(no cross-run to confirm whether the behaviour survived)",
                "Expected when the feature they covered was removed.",
                gone,
            ))

    # ---- skips -----------------------------------------------------------
    newly_skipped = head.skipped - base.skipped
    if newly_skipped:
        undocumented = sorted(
            t for t in newly_skipped
            if not _skip_is_documented(head.tests[t].message)
        )
        documented = sorted(newly_skipped - set(undocumented))

        if undocumented:
            findings.append(Finding(
                "skip_inflation",
                Severity.HIGH,
                f"{len(undocumented)} test(s) newly skipped without a reason "
                "that names an issue or an external cause",
                "Add a reason that points at a tracking issue and this stops "
                "being reported.",
                undocumented,
            ))
        if documented:
            findings.append(Finding(
                "skip_documented",
                Severity.INFO,
                f"{len(documented)} test(s) newly skipped with a documented "
                "reason",
                "Recorded so the skip is visible, not because it looks wrong.",
                documented,
            ))

    # ---- the suite got weaker in a way CI did not show -------------------
    # head is green but base was not failing here either: nothing to say.
    # This catches the inverse — the PR's own run hides errors.
    if head.collection_error:
        findings.append(Finding(
            "head_uncollectable",
            Severity.HIGH,
            "this pull request's own test suite could not be collected: "
            + head.collection_error.splitlines()[0],
            "",
        ))

    return findings


def summarise(base: RunResult, head: RunResult, cross: RunResult | None) -> dict:
    """The counts table that goes in the report."""
    table = {"base": base.counts(), "head": head.counts()}
    if cross is not None:
        table["crossrun"] = cross.counts()
    return table
