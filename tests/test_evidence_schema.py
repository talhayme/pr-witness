"""The evidence JSON the CLI writes must match the published schema.

The schema is the contract a verifier reads; evidence that drifts from it
is evidence nobody can check.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")

from pr_witness.claims import Claim, Verdict  # noqa: E402
from pr_witness.compare import Finding, Severity  # noqa: E402
from pr_witness.witness import Evidence  # noqa: E402

SCHEMA = json.loads((Path(__file__).parent.parent / "schema" / "evidence.v1.json").read_text())


def validate(payload: dict) -> None:
    jsonschema.Draft202012Validator(SCHEMA).validate(payload)


def full_evidence() -> Evidence:
    return Evidence(
        "a" * 40, "b" * 40, "pytest",
        counts={"base": {"collected": 3, "ran": 3, "passed": 3, "failed": 0, "skipped": 0},
                "head": {"collected": 3, "ran": 3, "passed": 3, "failed": 0, "skipped": 0},
                "crossrun": {"collected": 3, "ran": 3, "passed": 2, "failed": 1, "skipped": 0}},
        findings=[Finding("crossrun", Severity.HIGH, "one base test fails", "maybe intended",
                          ["tests/test_x::test_a"])],
        claims=[Claim("all_pass", "All tests pass", quote="All tests pass",
                      verdict=Verdict.MISLEADING, because="a base test fails")],
        notes=["checkwash not installed"],
    )


def test_evidence_validates_against_the_schema():
    validate(full_evidence().as_dict())


def test_empty_evidence_validates_too():
    validate(Evidence("a" * 40, "b" * 40, "vitest").as_dict())


def test_the_schema_is_strict_about_extra_fields():
    """additionalProperties: false — a verifier must not be handed surprises."""
    payload = full_evidence().as_dict()
    payload["surprise"] = 1
    with pytest.raises(jsonschema.ValidationError):
        validate(payload)


def test_tool_version_is_recorded():
    assert full_evidence().as_dict()["tool"] == {"name": "pr-witness", "version": __import__("pr_witness").__version__}


def test_ci_block_appears_only_inside_actions(monkeypatch):
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    assert "ci" not in full_evidence().as_dict()

    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    payload = full_evidence().as_dict()
    assert payload["ci"]["run_id"] == "123"
    validate(payload)


def test_gate_block_from_the_cli_validates(tmp_path):
    payload = full_evidence().as_dict()
    payload["gate"] = {"mode": "require-ack", "exit_code": 1, "reason": "x"}
    validate(payload)
