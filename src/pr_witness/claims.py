"""Extract claims from a pull request's prose and check them against the run.

A pull request description is a set of assertions about work that was done.
Most are unverifiable opinion; a few are checkable facts — "all 412 tests
pass", "added tests for parse_date", "no breaking changes" — and those are
the ones people read fastest and trust most.

Extraction is deterministic: regular expressions over a small set of
templates, in English and Russian. An LLM can be offered the leftovers later
(plan §8), but it never decides a verdict. A model that hallucinates a claim
the author did not make would be worse than no claim checking at all.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class Verdict(str, Enum):
    TRUE = "true"
    FALSE = "false"
    MISLEADING = "misleading"
    UNVERIFIABLE = "unverifiable"

    @property
    def mark(self) -> str:
        return {"true": "✓", "false": "✗", "misleading": "!", "unverifiable": "?"}[self.value]


@dataclass
class Claim:
    kind: str
    # The sentence the claim was found in, for context.
    text: str
    # The exact words that were matched. One sentence can carry two claims
    # ("All 3 tests pass, no breaking changes"), and quoting the whole
    # sentence twice hides which half each verdict is about.
    quote: str = ""
    verdict: Verdict = Verdict.UNVERIFIABLE
    # Why the verdict is what it is, in terms of what the run reported.
    because: str = ""
    # Captured groups the checker needs: counts, a referenced symbol, an issue.
    data: dict = field(default_factory=dict)

    @property
    def shown(self) -> str:
        """What to print: the matched words, falling back to the sentence."""
        return (self.quote or self.text).strip()

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "text": self.text.strip(),
            "quote": self.shown,
            "verdict": self.verdict.value,
            "because": self.because,
        }


# Every pattern is anchored on a number or a named thing, never on sentiment.
# "This should be much safer now" is not a claim anyone can check, and
# pretending otherwise would fill the report with noise.
#
# Russian included because the plan calls for it and because an agent writing
# a Russian description is not a rare case in this user's own repositories.
_PATTERNS: list[tuple[str, re.Pattern]] = [
    # "412 passed", "8 passed, 0 failed", "49/49 passing", "8 тестов прошли"
    ("count_passed", re.compile(
        r"(?P<n>\d+)\s*(?:/\s*(?P<total>\d+))?\s*"
        r"(?:tests?\s+)?(?:passed|passing|pass\b|green)",
        re.I)),
    ("count_passed", re.compile(
        r"(?P<n>\d+)\s*(?:из\s*(?P<total>\d+)\s*)?тест\w*\s*"
        r"(?:прош\w+|проходят|зелён\w+)",
        re.I)),
    # "all tests pass", "tests green", "все тесты проходят"
    ("all_pass", re.compile(
        r"\ball\s+(?:\d+\s+)?tests?\s+(?:still\s+)?(?:pass|passing|green)\b", re.I)),
    ("all_pass", re.compile(r"\btests?\s+(?:are\s+)?green\b", re.I)),
    ("all_pass", re.compile(
        r"\bsuite\s+(?:is\s+)?(?:green|passing|passes)\b", re.I)),
    ("all_pass", re.compile(r"\beverything\s+(?:is\s+)?green\b", re.I)),
    ("all_pass", re.compile(r"\bвсе\s+тесты\s+(?:проход\w+|зелён\w+)", re.I)),
    # "added 41 tests", "added 2 tests", "добавил 3 теста"
    ("count_added", re.compile(
        r"\badded\s+(?P<n>\d+)\s+(?:new\s+)?tests?\b", re.I)),
    ("count_added", re.compile(
        r"\bдобав\w+\s+(?P<n>\d+)\s+тест\w*", re.I)),
    # "Added `days_until` with 2 tests" — the count trails the subject.
    ("count_added", re.compile(
        r"\badded\s+.{0,40}?\bwith\s+(?P<n>\d+)\s+(?:new\s+)?tests?\b", re.I)),
    # "added test coverage", "added tests for parse_date"
    ("added_tests", re.compile(
        r"\badded\s+(?:new\s+)?tests?(?:\s+(?:for|covering)\s+[`\"']?(?P<subject>[\w./-]+))?",
        re.I)),
    ("added_tests", re.compile(r"\badded\s+test\s+coverage\b", re.I)),
    ("added_tests", re.compile(
        r"\bдобав\w+\s+тест\w*(?:\s+(?:для|на)\s+[`\"']?(?P<subject>[\w./-]+))?", re.I)),
    # "N tests collected", "N tests remain"
    ("count_collected", re.compile(
        r"(?P<n>\d+)\s+tests?\s+(?:collected|remain(?:ing)?)", re.I)),
    ("count_collected", re.compile(
        r"\bsame\s+(?P<n>\d+)\s+tests?\b", re.I)),
    # "no breaking changes", "no production code changed"
    ("no_breaking", re.compile(r"\bno\s+breaking\s+changes?\b", re.I)),
    ("no_breaking", re.compile(r"\bобратн\w+\s+совместим\w+", re.I)),
    ("no_prod_change", re.compile(
        r"\bno\s+production\s+code\s+(?:was\s+)?changed\b", re.I)),
    # "fixes #318", "fix #318", "исправляет #318"
    ("fixes_issue", re.compile(
        r"\b(?:fix(?:es|ed)?|closes?|resolves?)\s+#(?P<issue>\d+)", re.I)),
    ("fixes_issue", re.compile(
        r"\b(?:исправ\w+|закрыва\w+|чинит)\s+#(?P<issue>\d+)", re.I)),
]

# A heading like "## Fix #318" is a title, not an assertion about a test run.
# Counting it as a claim produced a false "unverifiable" on every case that
# names its issue in the heading.
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s")


def extract(text: str) -> list[Claim]:
    """Find the checkable assertions in a pull request description."""
    if not text:
        return []

    claims: list[Claim] = []
    seen: set[tuple[str, str]] = set()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or _HEADING.match(raw_line):
            continue

        for kind, pattern in _PATTERNS:
            for m in pattern.finditer(line):
                data = {k: v for k, v in m.groupdict().items() if v}
                key = (kind, m.group(0).lower())
                if key in seen:
                    continue
                seen.add(key)
                claims.append(Claim(kind=kind, text=line, quote=m.group(0), data=data))

    return _deduplicate(claims)


def _deduplicate(claims: list[Claim]) -> list[Claim]:
    """Drop the weaker of two claims that say the same thing.

    "Added 41 tests" matches both count_added and added_tests; reporting
    both would double-count one sentence.
    """
    by_line: dict[str, list[Claim]] = {}
    for c in claims:
        by_line.setdefault(c.text, []).append(c)

    out: list[Claim] = []
    for group in by_line.values():
        kinds = {c.kind for c in group}
        kept_kinds: set[str] = set()
        for c in group:
            # The counted form is strictly more checkable than the vague one.
            if c.kind == "added_tests" and "count_added" in kinds:
                continue
            if c.kind == "all_pass" and "count_passed" in kinds:
                continue
            # Two patterns of the same kind matching one sentence describe
            # one claim. Reporting it twice makes the author look twice as
            # careless as they were.
            if c.kind in kept_kinds:
                continue
            kept_kinds.add(c.kind)
            out.append(c)
    return out


def _green_but(base, head, affirmative: str, cross=None) -> tuple[Verdict, str]:
    """Is a true statement about a green run still the whole truth?

    "8 tests pass" can be literally correct while the base branch ran 14.
    The sentence is accurate and the impression it leaves is not, which is
    what `misleading` is for — the corpus labels these that way, and a
    checker that called them simply true would be the easiest thing in the
    world to game: narrow the suite, then quote the smaller number.

    Only tests that actually ran count on either side. A test skipped on
    both branches was never part of the denominator.
    """
    stopped = base.ran - head.ran
    if stopped:
        # Name the actual mechanism. "No longer runs" is true of a skipped
        # test and of a deleted one, and the author needs to know which.
        skipped_now = sorted(t for t in stopped if t in head.skipped)
        gone = sorted(t for t in stopped if t not in head.tests)
        if skipped_now and not gone:
            reason = f"{len(skipped_now)} test(s) are newly skipped and prove nothing"
        elif gone and not skipped_now:
            reason = f"{len(gone)} test(s) that ran on the base branch are gone"
        else:
            reason = (
                f"{len(stopped)} test(s) that ran on the base branch no longer run "
                f"({len(skipped_now)} skipped, {len(gone)} gone)"
            )
        return Verdict.MISLEADING, f"{affirmative}, but {reason}"
    # Everything the pull request's own suite can see is green. The base
    # branch's tests are the one remaining witness: if they fail here, the
    # suite is green because it was changed, not because the code is right.
    if cross is not None and not cross.collection_error:
        broken = base.passed & cross.failed
        if broken:
            return Verdict.MISLEADING, (
                f"{affirmative}, but {len(broken)} test(s) that passed on the "
                "base branch fail against this code"
            )
    return Verdict.TRUE, affirmative


def reconcile_with_findings(claims: list[Claim], findings) -> list[Claim]:
    """Temper a green claim that diff-level evidence contradicts.

    Some tampering leaves every count identical: an assertion wrapped in
    try/catch still runs, still passes, and still counts. The run cannot
    see it, so "all tests pass" is literally true and completely hollow.

    Only the findings that mean "a check stopped checking" are used here.
    A denominator note or a documented skip says nothing about whether the
    green is real, and borrowing them would make every claim misleading.
    """
    from pr_witness.compare import Severity

    HOLLOWING = {
        "broad_catch",
        "checkwash:ASSERT_REMOVED",
        "checkwash:ASSERT_WEAKENED",
        "checkwash:BROAD_EXCEPT_ADDED",
        "checkwash:TEST_PATCHES_SUBJECT",
        "checkwash:EXPECTED_VALUE_CHANGED",
    }
    hollowing = [
        f for f in findings
        if f.signal in HOLLOWING and f.severity in (Severity.HIGH, Severity.MEDIUM)
    ]
    if not hollowing:
        return claims

    for claim in claims:
        if claim.kind in ("all_pass", "count_passed") and claim.verdict is Verdict.TRUE:
            claim.verdict = Verdict.MISLEADING
            claim.because = (
                f"{claim.because}, but {len(hollowing)} assertion(s) were "
                f"weakened or neutralised in this change "
                f"({hollowing[0].signal})"
            )
    return claims


# Claims about the whole suite that a run restricted to some files cannot
# judge. "3128 passed" against a run of five files is not false, it is
# unmeasured — and the first real case said "false". Scoped claims (a named
# test was added, no production file changed) are unaffected.
_WHOLE_SUITE = {"count_passed", "all_pass", "count_collected", "no_breaking"}


def check(claims: list[Claim], base, head, cross=None, restricted: bool = False) -> list[Claim]:
    """Give every claim a verdict, using what the runs actually reported.

    `base`, `head` and `cross` are RunResult objects. Nothing here guesses:
    a claim whose truth the runs cannot establish stays `unverifiable`, which
    is a real answer and often the most useful one. `restricted` says the
    runs covered only some test files (--paths / --changed-only).
    """
    for claim in claims:
        kind = claim.kind

        if restricted and kind in _WHOLE_SUITE:
            claim.verdict = Verdict.UNVERIFIABLE
            claim.because = ("the run was restricted to the test files the change touched; "
                             "a whole-suite count cannot be checked against it")
            continue

        if kind == "count_passed":
            stated = int(claim.data["n"])
            actual = len(head.passed)
            total = claim.data.get("total")
            if stated != actual:
                # A number lifted from the wrong part of pytest's summary —
                # the collected total rather than the passed count — is
                # inaccurate, not invented. `false` is for a figure the run
                # contradicts outright; this one is misleading.
                # ...but only when nothing actually failed. A green-sounding
                # number quoted over a red run is a false statement, whatever
                # line of the summary it came from.
                quoted_something_real = not head.failed and stated in (
                    head.collected, len(head.ran), base.collected, len(base.passed),
                )
                if quoted_something_real:
                    claim.verdict = Verdict.MISLEADING
                    claim.because = (
                        f"{stated} were collected, but only {actual} passed"
                        + (f"; {len(head.skipped)} skipped" if head.skipped else "")
                    )
                else:
                    claim.verdict = Verdict.FALSE
                    claim.because = (
                        f"the run reports {actual} passed"
                        + (f" and {len(head.failed)} failed" if head.failed else "")
                    )
            elif total is not None and int(total) != head.collected:
                claim.verdict = Verdict.FALSE
                claim.because = f"the run collected {head.collected}, not {total}"
            else:
                claim.verdict, claim.because = _green_but(
                    base, head, f"{actual} passed in the run", cross,
                )

        elif kind == "all_pass":
            if head.failed:
                claim.verdict = Verdict.FALSE
                claim.because = f"{len(head.failed)} test(s) fail in the run"
            else:
                claim.verdict, claim.because = _green_but(
                    base, head, f"all {len(head.passed)} collected tests pass", cross,
                )

        elif kind == "count_added":
            stated = int(claim.data["n"])
            added = len(set(head.tests) - set(base.tests))
            if added == stated:
                claim.verdict = Verdict.TRUE
                claim.because = f"{added} new test(s) in the run"
            else:
                claim.verdict = Verdict.FALSE
                claim.because = (
                    f"the run shows {added} new test(s), not {stated}"
                )

        elif kind == "added_tests":
            added = sorted(set(head.tests) - set(base.tests))
            subject = claim.data.get("subject")
            if not added:
                claim.verdict = Verdict.FALSE
                claim.because = "no new tests appear in the run"
            elif subject:
                # The weakest check in here, and deliberately so: a test that
                # mentions the subject in its own name is evidence, its
                # absence is not proof. Hence misleading rather than false.
                hit = [t for t in added if subject.lower() in t.lower()]
                if hit:
                    claim.verdict = Verdict.TRUE
                    claim.because = (
                        f"{len(hit)} new test(s) name `{subject}`"
                    )
                else:
                    claim.verdict = Verdict.MISLEADING
                    claim.because = (
                        f"{len(added)} new test(s), but none names `{subject}` — "
                        "it may still be covered indirectly"
                    )
            else:
                claim.verdict = Verdict.TRUE
                claim.because = f"{len(added)} new test(s) in the run"

        elif kind == "count_collected":
            stated = int(claim.data["n"])
            if stated == head.collected:
                claim.verdict = Verdict.TRUE
                claim.because = f"{head.collected} collected"
            else:
                claim.verdict = Verdict.FALSE
                claim.because = f"the run collected {head.collected}, not {stated}"

        elif kind == "no_breaking":
            if cross is None:
                claim.because = "no cross-run was performed"
            elif cross.collection_error:
                claim.verdict = Verdict.MISLEADING
                claim.because = (
                    "the base branch's tests no longer collect against this code"
                )
            elif (broken := base.passed & cross.failed):
                claim.verdict = Verdict.FALSE
                claim.because = (
                    f"{len(broken)} test(s) that passed on the base branch now fail"
                )
            else:
                claim.verdict = Verdict.TRUE
                claim.because = "every base-branch test still passes on this code"

        elif kind == "no_prod_change":
            # Decided by the diff, not by the run; filled in by the caller
            # which has the changed-file list.
            claim.because = "needs the file list"

        elif kind == "fixes_issue":
            # Whether a fix is real is not something a test run can answer.
            # Saying so plainly is more honest than inventing a heuristic.
            claim.verdict = Verdict.UNVERIFIABLE
            claim.because = (
                "whether this fixes the issue cannot be determined from the "
                "test run"
            )

    return claims


def check_no_prod_change(claim: Claim, changed_files: list[str], test_globs=None) -> Claim:
    """Resolve a 'no production code changed' claim against the diff."""
    from pr_witness.git_ops import DEFAULT_TEST_GLOBS, matches_glob

    patterns = test_globs or DEFAULT_TEST_GLOBS
    production = [
        f for f in changed_files
        if not any(matches_glob(f, p) for p in patterns)
    ]
    if production:
        claim.verdict = Verdict.FALSE
        shown = ", ".join(production[:3])
        more = f" and {len(production) - 3} more" if len(production) > 3 else ""
        claim.because = f"production files changed: {shown}{more}"
    else:
        claim.verdict = Verdict.TRUE
        claim.because = "only test files changed"
    return claim
