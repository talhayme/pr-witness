"""What the exit code should be, given the evidence and the mode.

Three modes, from the plan:

    report       never fail. The default, because a tool that blocks on its
                 first day gets uninstalled on its second.
    require-ack  fail on a flag until a human adds the approval label. The
                 tool raises its hand; a maintainer lowers it.
    strict       fail on a flag, label or not. A disproved claim is a
                 disproved claim.

Kept apart from the CLI and the report so it can be tested with no git, no
runner and no network: a wrong exit code here breaks every pipeline that
trusts it.
"""

from __future__ import annotations

from dataclasses import dataclass

from pr_witness.compare import Severity

MODES = ("report", "require-ack", "strict")
APPROVAL_LABEL = "test-change-approved"


@dataclass(frozen=True)
class Decision:
    exit_code: int
    reason: str


def decide(evidence, mode: str, approved: bool = False) -> Decision:
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")

    false_claims = [c for c in evidence.claims if c.verdict.value == "false"]
    high = [f for f in evidence.findings if f.severity is Severity.HIGH]
    flagged = bool(false_claims) or bool(high)

    if mode == "report":
        return Decision(0, "report mode never fails")

    if not flagged:
        return Decision(0, "nothing at flag level")

    what = []
    if false_claims:
        what.append(f"{len(false_claims)} disproved claim(s)")
    if high:
        what.append(f"{len(high)} high finding(s)")
    summary = " and ".join(what)

    if mode == "require-ack":
        if approved:
            return Decision(0, f"{summary}, approved via `{APPROVAL_LABEL}`")
        return Decision(1, f"{summary}; add `{APPROVAL_LABEL}` to acknowledge")

    # strict: the label documents intent, it does not change the facts.
    if approved:
        return Decision(1, f"{summary}; strict mode does not honour `{APPROVAL_LABEL}`")
    return Decision(1, summary)
