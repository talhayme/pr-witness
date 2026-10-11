"""Exit codes per mode. No git, no runner: a wrong code here breaks pipelines."""

from __future__ import annotations

import pytest

from pr_witness.claims import Claim, Verdict
from pr_witness.compare import Finding, Severity
from pr_witness.gate import APPROVAL_LABEL, decide
from pr_witness.witness import Evidence


def evidence(findings=(), claims=()):
    return Evidence("a" * 40, "b" * 40, "pytest", findings=list(findings), claims=list(claims))


HIGH = Finding("crossrun", Severity.HIGH, "a base test fails")
MEDIUM = Finding("denominator_removed", Severity.MEDIUM, "tests gone")
LIE = Claim("count_passed", "412 passed", verdict=Verdict.FALSE)
SPIN = Claim("all_pass", "all tests pass", verdict=Verdict.MISLEADING)


def test_report_mode_never_fails():
    assert decide(evidence([HIGH], [LIE]), "report").exit_code == 0


@pytest.mark.parametrize("mode", ["require-ack", "strict"])
def test_clean_evidence_passes_every_mode(mode):
    assert decide(evidence(), mode).exit_code == 0


@pytest.mark.parametrize("mode", ["require-ack", "strict"])
def test_medium_findings_and_misleading_claims_do_not_fail(mode):
    """Flags are HIGH findings and disproved claims; everything else is a note."""
    assert decide(evidence([MEDIUM], [SPIN]), mode).exit_code == 0


def test_require_ack_fails_on_a_flag_until_the_label_is_applied():
    d = decide(evidence([HIGH]), "require-ack")
    assert d.exit_code == 1
    assert APPROVAL_LABEL in d.reason
    assert decide(evidence([HIGH]), "require-ack", approved=True).exit_code == 0


def test_a_disproved_claim_is_a_flag_on_its_own():
    assert decide(evidence(claims=[LIE]), "require-ack").exit_code == 1


def test_strict_does_not_honour_the_label():
    d = decide(evidence(claims=[LIE]), "strict", approved=True)
    assert d.exit_code == 1
    assert "strict" in d.reason


def test_unknown_mode_is_refused_loudly():
    with pytest.raises(ValueError):
        decide(evidence(), "lenient")


@pytest.mark.parametrize("signal", sorted(__import__("pr_witness.compare", fromlist=["x"]).REVIEW_SIGNALS))
def test_every_review_signal_holds_the_job_and_matches_the_verdict(signal):
    """0.3.0 said `review` for three of these and let the job through:
    the gate kept its own one-item list. The verdict and the gate now read
    the same one."""
    ev = evidence([Finding(signal, Severity.MEDIUM, "to review")])
    assert ev.verdict == "review"
    assert decide(ev, "require-ack").exit_code == 1
    assert decide(ev, "require-ack", approved=True).exit_code == 0
    assert decide(ev, "strict").exit_code == 1


def test_a_review_signal_reported_below_medium_does_not_hold_the_job():
    ev = evidence([Finding("checkwash:EXPECTED_VALUE_CHANGED", Severity.LOW, "advisory")])
    assert ev.verdict == "clean" and decide(ev, "strict").exit_code == 0
