"""Diff-level integrity: checkwash, plus the three gaps it has not closed.

checkwash does this job well and publishes its own benchmarks. pr-witness
does not re-implement it and does not compete with it — it shells out to it
and normalises the result into one schema alongside the run-level findings,
so a reviewer reads one report instead of two.

What is implemented here is only what checkwash 0.6.0 does not do, measured
rather than assumed (see docs/upstream/README.md). Each one is written up as
a proposal to checkwash first; this is the stopgap, not a fork.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from pr_witness.compare import Finding, Severity

# checkwash's own severities, mapped onto ours.
#
# The mapping is deliberately lossy at the bottom. checkwash blocks only on
# `high` and `critical`; its `warn` findings are advisory, and it raises one
# for every disappeared test — which means every honest rename, module split
# and parametrised collapse produces a handful of them.
#
# Measured on the corpus: mapping `warn` to MEDIUM dropped precision from
# 0.90 to 0.75, all of it from honest refactors. Mapping it to LOW keeps the
# finding visible in the report without asserting that anything is wrong,
# which is exactly what checkwash itself does with it.
_SEVERITY = {
    "critical": Severity.HIGH,
    "high": Severity.HIGH,
    "warn": Severity.LOW,
    "info": Severity.INFO,
}

# Why each checkwash rule might be innocent. Its own messages explain what
# was found; these explain when that is fine, which is the thing a flagged
# author most needs to read.
_INNOCENT = {
    "ASSERT_REMOVED": "Legitimate when the behaviour it checked was removed.",
    "ASSERT_WEAKENED": "Legitimate when the previous assertion was too strict — "
                       "a float comparison that was always luck, for instance.",
    "TEST_DISABLED": "Legitimate with a reason that names a tracking issue.",
    "TEST_PATCHES_SUBJECT": "Legitimate when the mock stands in for a boundary "
                            "(network, clock, filesystem) rather than for the "
                            "code under test.",
    "CI_WORKFLOW_TOUCHED": "Legitimate when the change makes CI stricter, or "
                           "moves a step rather than weakening it.",
    "BROAD_EXCEPT_ADDED": "Legitimate when the except asserts on the error.",
    "TOLERANCE_LOOSENED": "Legitimate when the old tolerance was unrealistic "
                          "for the platform.",
}


def checkwash_command() -> list[str] | None:
    """How to invoke checkwash, or None if it is not installed.

    `shutil.which` alone is not enough: when pr-witness runs from a
    virtualenv that is on sys.path but not on PATH — which is what happens
    whenever it is invoked as a library, or by a CI step that does not
    activate the environment — the executable is invisible while the module
    imports fine. Falling back to `python -m` makes the common case work
    instead of silently skipping half the checks.
    """
    exe = shutil.which("checkwash")
    if exe:
        return [exe]
    # Prefer the interpreter running us: that is the environment pr-witness
    # itself was installed into, so checkwash is most likely beside it.
    for candidate in (Path(sys.executable).parent / "checkwash",):
        if candidate.exists():
            return [str(candidate)]
    if importlib.util.find_spec("checkwash") is not None:
        return [sys.executable, "-m", "checkwash"]
    return None


def checkwash_available() -> bool:
    return checkwash_command() is not None


def translate(item: dict, documented: set[str]) -> Finding:
    """One checkwash finding as one of ours — its observation, our rating."""
    rule = item.get("rule", "UNKNOWN")
    path = item.get("path", "")
    unit = item.get("unit") or ""
    where = f"{path}::{unit}" if unit else path
    severity = _SEVERITY.get(item.get("severity", "warn"), Severity.MEDIUM)
    innocent = _INNOCENT.get(rule, "")

    # Two places where pr-witness takes checkwash's observation and not
    # its rating. Both came from running a frozen tool on seventeen real
    # commits: every flag it raised was on an honest one, and these two
    # rules raised three of the four. Reported, with the disagreement
    # stated; never dropped.
    if rule in _REWRITE_RULES and severity is Severity.HIGH:
        severity = Severity.MEDIUM
        innocent = (
            "checkwash rates a rewritten expectation high. pr-witness holds it "
            "at review: neither a static rule nor a run can tell an intended "
            "change of behaviour from a test bent to fit a bug, so a human "
            "reads it. If your policy is that expected values must not change "
            "alongside the code, trust checkwash here."
        )
    if rule == "GUARDRAIL_TOUCHED" and severity is Severity.HIGH:
        severity = Severity.MEDIUM
        innocent = (
            "checkwash rates any change to an agent instruction file high. "
            "pr-witness reports it without flagging: in a repository developed "
            "with an agent these files change in ordinary work. If yours must "
            "not change in a pull request, trust checkwash here."
        )

    # checkwash reports every added skip marker as TEST_DISABLED. It starts
    # at `warn` and is raised to `high` only when nothing in the diff
    # explains it (SPEC §5: a compatibility gate or a plausible production
    # change holds it at `warn`). It deliberately does not read the skip's
    # reason — a phrase that earns credit is a phrase an agent will learn to
    # write (checkwash#364). We disagree on exactly one point: a skip whose
    # reason names a tracking issue is treated here as a decision someone
    # made and can be held to. Against an agent that writes plausible
    # reasons, checkwash's position is the stronger one; this is ours to
    # revisit.
    #
    # Downgraded rather than dropped, and the disagreement is stated in
    # the report. Silently discarding another tool's finding would make
    # this one harder to trust, not easier.
    if rule == "TEST_DISABLED" and unit and _matches_documented(unit, documented):
        severity = Severity.INFO
        innocent = (
            "checkwash reports this added skip and does not read skip reasons, "
            "because an agent can learn to write them. pr-witness does not flag "
            "it: the run shows a reason that names an issue or an external "
            "cause. If an agent writing plausible reasons is in your threat "
            "model, trust checkwash here, not us."
        )

    return Finding(
        signal=f"checkwash:{rule}",
        severity=severity,
        summary=item.get("message", rule),
        innocent_explanation=innocent,
        tests=[where] if where else [],
    )


def run_checkwash(
    repo: Path, base: str, head: str, timeout: int = 300,
    documented_skips: set[str] | None = None,
) -> tuple[list[Finding], str]:
    """Run checkwash and translate its findings into ours.

    Returns (findings, note). A note rather than an exception when checkwash
    is absent or fails: its absence degrades the report, it does not
    invalidate the cross-run, which is our own contribution.
    """
    command = checkwash_command()
    if command is None:
        return [], ("checkwash not installed; diff-level integrity not checked "
                    "(pip install checkwash)")

    try:
        proc = subprocess.run(
            [*command, "check", f"{base}..{head}", "--format", "json"],
            cwd=repo, capture_output=True, text=True, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [], f"checkwash did not complete: {exc}"

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
        return [], "checkwash produced no readable output: " + " ".join(tail)

    documented = documented_skips or set()
    findings = [translate(item, documented) for item in data.get("findings", [])]
    return findings, ""


# checkwash's rules that say "the expectation was rewritten" — as opposed to
# removed, weakened or disabled, which stay high unless the run corroborates.
_REWRITE_RULES = frozenset({
    "EXPECTED_VALUE_CHANGED", "ASSERT_SUBSTITUTED", "EXPECTED_VALUE_HARDCODED", "SUBJECT_INPUT_CHANGED",
})

# Run findings that tell one test's story; coverage_replaced is about
# functions, not tests, so it corroborates nothing here.
RUN_STORIES = ("expectation_changed", "tests_removed_still_passing", "greened_by_test_edit")


def reconcile_with_run(cw_findings: list[Finding], run_findings: list[Finding]) -> None:
    """Fold a static finding onto the run's own evidence about the same test.

    When the cross-run has already shown what happened to a test — its old
    assertion fails on the new code (`expectation_changed`), or it was
    deleted and still passes (`tests_removed_still_passing`) — checkwash's
    EXPECTED_VALUE_CHANGED / ASSERT_REMOVED / TEST_DISABLED on that same test
    is the same fact seen statically: corroboration, not a second, louder
    reason. Left at `high` it turned every honest specification change and
    every deliberate test removal into a flag. It is capped at the level of
    the run finding so the verdict stays `review`, and the report says so.
    Nothing is dropped; a static finding the run does not corroborate keeps
    checkwash's own rating.
    """
    shown = {
        _unit_of(t) for f in run_findings
        if f.signal in RUN_STORIES for t in f.tests
    }
    if not shown:
        return
    static = {"checkwash:EXPECTED_VALUE_CHANGED", "checkwash:ASSERT_REMOVED", "checkwash:TEST_DISABLED", "checkwash:ASSERT_WEAKENED"}
    for f in cw_findings:
        if f.signal in static and f.severity is Severity.HIGH and any(_unit_of(t) in shown for t in f.tests):
            f.severity = Severity.MEDIUM
            f.innocent_explanation = (
                "checkwash rates this high. pr-witness holds it at review here: the run "
                "already shows what happened to this test, and the report carries it. "
                "Same fact, seen twice — a reviewer decides, not a second flag."
            )


def _unit_of(node_id: str) -> str:
    """`tests/test_x.py::TestA::test_y[param]` → `test_y`; checkwash's `TestA.test_y` → `test_y`."""
    last = node_id.rsplit("::", 1)[-1].split("[", 1)[0]
    if "." in last and " " not in last:
        last = last.rsplit(".", 1)[-1]
    return last


def _matches_documented(unit: str, documented: set[str]) -> bool:
    """Does this checkwash unit name a test we saw skipped with a reason?

    The two tools name tests differently — checkwash uses the qualname from
    the source, we use the runner's node id — so this compares the final
    segment, which is the test function's own name in both.
    """
    name = unit.rsplit("::", 1)[-1].rsplit(".", 1)[-1]
    return any(node.rsplit("::", 1)[-1] == name for node in documented)


# --------------------------------------------------------------------------
# The three gaps. See docs/upstream/ for the proposals these implement.
# --------------------------------------------------------------------------

_TEST_FILE = re.compile(r"\.(test|spec)\.[jt]sx?$")

# Lint rules that enforce that a test actually tests something. Disabling
# one of these is a verification-layer change; disabling `no-unused-vars` is
# not, and reporting it would be noise.
_VERIFICATION_LINT_RULES = {
    "jest/no-disabled-tests",
    "jest/no-conditional-expect",
    "jest/expect-expect",
    "jest/no-commented-out-tests",
    "jest/no-focused-tests",
    "jest/valid-expect",
    "vitest/no-disabled-tests",
    "vitest/no-conditional-expect",
    "vitest/expect-expect",
    "vitest/no-commented-out-tests",
    "vitest/no-focused-tests",
    "vitest/valid-expect",
    "testing-library/await-async-utils",
}

_ASSERT_CALL = re.compile(r"\b(expect|assert)\s*[\(.]")
_SUPPRESS_TS = re.compile(r"@ts-(ignore|expect-error|nocheck)\b")
# The rule list runs to the end of the comment. Excluding `/` here would
# truncate every plugin rule at its slash — `vitest/expect-expect` became
# `vitest`, and the detector matched nothing at all.
_ESLINT_DISABLE = re.compile(
    r"eslint-disable(?:-next-line|-line)?\s+([^\n]*?)(?:\*/|$)"
)


def _added_lines(diff: str) -> list[tuple[str, str]]:
    """(path, line) for every added line in a unified diff."""
    out, path = [], ""
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            out.append((path, line[1:]))
    return out


def _catch_swallows_assertion(body: str) -> bool:
    """Does this catch block let the error pass silently?

    A catch that asserts on the error is the legitimate "this should throw"
    pattern. One that rethrows is fine too. Anything else swallows.
    """
    stripped = re.sub(r"//[^\n]*|/\*.*?\*/", "", body, flags=re.S).strip()
    if not stripped:
        return True
    if re.search(r"\b(throw|rethrow)\b", stripped):
        return False
    if _ASSERT_CALL.search(stripped):
        return False
    # console.warn(e); return; — still swallowing.
    return True


def drop_covered_by_checkwash(js_findings: list[Finding], cw_findings: list[Finding]) -> list[Finding]:
    """Remove our try/catch finding where checkwash already reported the same file.

    checkwash 0.7.0 reports an assertion swallowed by a `try`/`catch` as
    BROAD_EXCEPT_ADDED (checkwash#363). The JS/TS check here predates that;
    it stays for older checkwash and for files checkwash did not report, and
    steps aside where it would only repeat checkwash, whose rating stands.
    """
    covered = {t.split("::", 1)[0] for f in cw_findings if f.signal == "checkwash:BROAD_EXCEPT_ADDED" for t in f.tests}
    return [f for f in js_findings if not (f.signal == "broad_catch" and f.tests and set(f.tests) <= covered)]


def detect_js_gaps(repo: Path, base: str, head: str) -> list[Finding]:
    """JS/TS patterns checkwash did not report as of 0.6.0.

    `@ts-nocheck`, `@ts-ignore` and `eslint-disable` are still unreported in
    checkwash 0.7.0 (checkwash#366, #367). The try/catch case is reported
    there since 0.7.0; `drop_covered_by_checkwash` avoids saying it twice.
    """
    try:
        diff = subprocess.run(
            ["git", "diff", "--unified=3", f"{base}..{head}", "--", "*.ts", "*.tsx", "*.js", "*.jsx"],
            cwd=repo, capture_output=True, text=True, timeout=120,
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []

    findings: list[Finding] = []
    ts_ignores: list[str] = []
    nochecks: list[str] = []
    lint_disables: list[str] = []

    for path, line in _added_lines(diff):
        if not _TEST_FILE.search(path):
            continue

        if (m := _SUPPRESS_TS.search(line)):
            if m.group(1) == "nocheck":
                nochecks.append(path)
            else:
                ts_ignores.append(path)

        if (m := _ESLINT_DISABLE.search(line)):
            rules = {r.strip() for r in (m.group(1) or "").split(",") if r.strip()}
            matched = rules & _VERIFICATION_LINT_RULES
            if matched:
                lint_disables.append(f"{path}: {', '.join(sorted(matched))}")
            elif not rules:
                # A bare `eslint-disable` names no rules, which means all of
                # them — including the ones that enforce that a test asserts
                # something.
                lint_disables.append(f"{path}: all rules")

    # try/catch needs the whole file, not the diff: a catch block added
    # around an existing assertion shows only its own two lines in the diff.
    for path in {p for p, _ in _added_lines(diff) if _TEST_FILE.search(p)}:
        try:
            after = subprocess.run(
                ["git", "show", f"{head}:{path}"],
                cwd=repo, capture_output=True, text=True, timeout=60,
            ).stdout
            before = subprocess.run(
                ["git", "show", f"{base}:{path}"],
                cwd=repo, capture_output=True, text=True, timeout=60,
            ).stdout
        except (OSError, subprocess.TimeoutExpired):
            continue

        added = _count_swallowing_catches(after) - _count_swallowing_catches(before)
        if added > 0:
            findings.append(Finding(
                "broad_catch",
                Severity.HIGH,
                f"{path}: {added} try/catch block(s) added around an assertion, "
                "with a catch that neither rethrows nor asserts — the test now "
                "passes whatever happens",
                "Legitimate when the catch asserts on the error, which is the "
                "'this should throw' pattern.",
                [path],
            ))

    if nochecks:
        findings.append(Finding(
            "ts_suppression",
            Severity.HIGH,
            f"@ts-nocheck added to {len(nochecks)} test file(s), disabling type "
            "checking for every test in them",
            "",
            sorted(set(nochecks)),
        ))
    if ts_ignores:
        findings.append(Finding(
            "ts_suppression",
            Severity.MEDIUM,
            f"{len(ts_ignores)} type suppression(s) added in test files",
            "Legitimate for a third-party type bug, or a test that deliberately "
            "passes an invalid value.",
            sorted(set(ts_ignores)),
        ))
    if lint_disables:
        findings.append(Finding(
            "lint_suppression",
            Severity.MEDIUM,
            f"{len(lint_disables)} lint rule(s) that enforce test quality "
            "disabled in test files",
            "Legitimate when the rule is wrong about this specific case — say "
            "so in a comment next to it.",
            sorted(set(lint_disables)),
        ))

    return findings


def _count_swallowing_catches(source: str) -> int:
    """How many catch blocks in this file swallow an assertion.

    A brace-counting scan rather than a parser. The cost of a real TS parser
    (a node dependency, or a Python TS grammar) is not worth paying for one
    detector that exists only until checkwash takes it; the failure mode is
    a missed finding, not a false one.
    """
    count = 0
    for m in re.finditer(r"\btry\s*\{", source):
        depth, i = 0, m.end() - 1
        while i < len(source):
            if source[i] == "{":
                depth += 1
            elif source[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        try_body = source[m.end():i]
        if not _ASSERT_CALL.search(try_body):
            continue

        rest = source[i + 1:]
        cm = re.match(r"\s*catch\s*(\([^)]*\))?\s*\{", rest)
        if not cm:
            continue
        depth, j = 0, cm.end() - 1
        while j < len(rest):
            if rest[j] == "{":
                depth += 1
            elif rest[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if _catch_swallows_assertion(rest[cm.end():j]):
            count += 1
    return count
