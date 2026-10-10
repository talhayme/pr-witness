"""Orchestration: three runs, one comparison, one piece of evidence."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from pr_witness import claims as claims_mod
from pr_witness import git_ops, integrity, runners
from pr_witness.compare import Finding, Severity, compare, summarise
from pr_witness.results import RunResult


@dataclass
class Evidence:
    base_sha: str
    head_sha: str
    runner: str
    counts: dict = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    claims: list = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        """What a gate would do. Reporting is the default; this is advisory."""
        # A disproved claim is the strongest and most legible signal there
        # is: the description says one thing and the run says another, with
        # no interpretation in between.
        if any(c.verdict.value == "false" for c in self.claims):
            return "flag"
        if any(f.severity is Severity.HIGH for f in self.findings):
            return "flag"
        if any(f.severity is Severity.MEDIUM for f in self.findings):
            return "note"
        return "clean"

    def as_dict(self) -> dict:
        return {
            "schema": "pr-witness/evidence/v1",
            "base": self.base_sha,
            "head": self.head_sha,
            "runner": self.runner,
            "counts": self.counts,
            "verdict": self.verdict,
            "findings": [f.as_dict() for f in self.findings],
            "claims": [c.as_dict() for c in self.claims],
            "notes": self.notes,
        }


def _env_for(tree: Path, repo: Path) -> dict[str, str]:
    """Environment for a run inside a throwaway worktree.

    A worktree has no node_modules or virtualenv of its own. Rather than
    installing dependencies three times, point the run at the ones the
    repository already has.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(tree), env.get("PYTHONPATH", "")) if p
    )
    node_modules = repo / "node_modules"
    if node_modules.exists() and not (tree / "node_modules").exists():
        try:
            (tree / "node_modules").symlink_to(node_modules)
        except OSError:
            pass
    return env


def witness(
    repo: Path,
    base: str = "origin/main",
    head: str = "HEAD",
    runner_name: str | None = None,
    skip_crossrun: bool = False,
    skip_integrity: bool = False,
    pr_body: str = "",
    timeout: int = 1800,
    keep_reports: Path | None = None,
) -> Evidence:
    repo = git_ops.repo_root(repo)
    head_sha = git_ops.resolve(head, cwd=repo)
    base_sha = git_ops.merge_base(base, head, cwd=repo)

    name = runner_name or runners.detect(repo) or "pytest"
    runner = runners.RUNNERS[name]
    notes: list[str] = []

    if base_sha == head_sha:
        notes.append("base and head are the same commit; nothing to compare")
        return Evidence(base_sha, head_sha, name, notes=notes)

    # Commit messages are a claim source too (plan §8): an agent that says
    # nothing in the description often says it in the commit.
    claim_text = pr_body
    if not claim_text.strip():
        claim_text = git_ops.git(
            "log", "--format=%B", f"{base_sha}..{head_sha}", cwd=repo, check=False,
        )

    # Reports go to a temporary directory, not into the repository. A tool
    # that leaves artefacts in someone's checkout gets run once.
    with tempfile.TemporaryDirectory(prefix="pr-witness-reports-") as tmp:
        reports = Path(keep_reports) if keep_reports else Path(tmp)
        reports.mkdir(parents=True, exist_ok=True)

        def _run(rev_tree: Path, label: str) -> RunResult:
            return runners.run(
                runner, rev_tree, reports / f"{label}.xml",
                timeout=timeout, env=_env_for(rev_tree, repo),
            )

        with git_ops.worktree(base_sha, repo) as tree:
            base_run = _run(tree, "base")
        with git_ops.worktree(head_sha, repo) as tree:
            head_run = _run(tree, "head")

        cross_run = None
        if skip_crossrun:
            notes.append("cross-run skipped by request")
        else:
            with git_ops.crossrun_tree(base_sha, head_sha, repo) as tree:
                cross_run = _run(tree, "crossrun")

    findings = compare(base_run, head_run, cross_run)

    # Diff-level integrity, from checkwash plus the gaps it has not closed.
    # Deliberately last: the cross-run is our own contribution, and a missing
    # checkwash must degrade the report rather than break it.
    if not skip_integrity:
        # Tell checkwash which skips the run showed to be documented, so the
        # one place the two tools disagree is reconciled explicitly.
        documented = {
            node for f in findings if f.signal == "skip_documented" for node in f.tests
        }
        cw_findings, note = integrity.run_checkwash(
            repo, base_sha, head_sha, documented_skips=documented,
        )
        findings += cw_findings
        if note:
            notes.append(note)
        findings += integrity.detect_js_gaps(repo, base_sha, head_sha)

    # Highest severity first, then by signal, so the report opens with the
    # thing most worth reading.
    order = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2, Severity.INFO: 3}
    findings.sort(key=lambda f: (order[f.severity], f.signal))

    checked = claims_mod.check(
        claims_mod.extract(claim_text), base_run, head_run, cross_run,
    )
    # A green run proves nothing about assertions that were neutralised in
    # the diff, so the claim verdicts are tempered by what the diff showed.
    checked = claims_mod.reconcile_with_findings(checked, findings)
    for claim in checked:
        if claim.kind == "no_prod_change":
            claims_mod.check_no_prod_change(
                claim, git_ops.changed_files(base_sha, head_sha, cwd=repo),
            )

    return Evidence(
        base_sha=base_sha,
        head_sha=head_sha,
        runner=name,
        counts=summarise(base_run, head_run, cross_run),
        findings=findings,
        claims=checked,
        notes=notes,
    )
