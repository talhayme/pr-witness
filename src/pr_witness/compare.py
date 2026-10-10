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


def _skip_is_documented(message: str) -> bool:
    text = (message or "").strip().lower()
    if len(text) < 8:
        return False
    return any(marker in text for marker in _ISSUE_MARKERS)


def _test_file_of(node_id: str) -> str:
    """`tests/test_dates::test_monday` → `tests/test_dates`; `cart.test.ts::x` → `cart.test.ts`."""
    return node_id.split("::", 1)[0]


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
