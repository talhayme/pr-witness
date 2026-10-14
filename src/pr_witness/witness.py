"""Orchestration: three runs, one comparison, one piece of evidence."""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from pr_witness import __version__
from pr_witness import claims as claims_mod
from pr_witness import coverage, git_ops, integrity, runners
from pr_witness.compare import Finding, Severity, compare, is_review, summarise
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
        # A rewritten test whose old version fails: honest or not, a human
        # has to look. Louder than a note, quieter than a flag.
        if any(is_review(f) for f in self.findings):
            return "review"
        if any(f.severity is Severity.MEDIUM for f in self.findings):
            return "note"
        return "clean"

    def as_dict(self) -> dict:
        payload = {
            "schema": "pr-witness/evidence/v1",
            "base": self.base_sha,
            "head": self.head_sha,
            "runner": self.runner,
            "counts": self.counts,
            "verdict": self.verdict,
            "findings": [f.as_dict() for f in self.findings],
            "claims": [c.as_dict() for c in self.claims],
            "notes": self.notes,
            "tool": {"name": "pr-witness", "version": __version__},
        }
        # Inside Actions, record which run produced this. The signature
        # proves the file was not altered; this says where to look for the
        # logs that produced it.
        if os.environ.get("GITHUB_RUN_ID"):
            payload["ci"] = {
                "provider": "github-actions",
                "repository": os.environ.get("GITHUB_REPOSITORY", ""),
                "run_id": os.environ["GITHUB_RUN_ID"],
                "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
                "workflow": os.environ.get("GITHUB_WORKFLOW", ""),
            }
        return payload


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


def _assertion_diffs(repo: Path, base: str, head: str, base_run, cross_run, changed_tests: set[str]) -> dict[str, str]:
    """For each base test the PR rewrote and that now fails, the hunk that changed it.

    Shown next to the finding so a reviewer sees the one line that matters —
    the old assertion and the new one — without opening the diff.
    """
    if cross_run is None or not changed_tests:
        return {}
    out: dict[str, str] = {}
    regressed = base_run.passed & cross_run.failed
    for node in regressed:
        fn = node.rsplit("::", 1)[-1].split("[", 1)[0]
        for path in changed_tests:
            try:
                diff = git_ops.git("diff", "--unified=2", f"{base}..{head}", "--", path, cwd=repo, check=False)
            except Exception:  # noqa: BLE001
                continue
            if not diff:
                continue
            # keep only hunks mentioning the test function
            hunks = re.split(r"(?m)^(?=@@ )", diff)
            keep = [h for h in hunks if fn in h and h.startswith("@@")]
            if keep:
                body = "\n".join(l for h in keep for l in h.splitlines() if l.startswith(("@@", "+", "-")) and not l.startswith(("+++", "---")))
                out[node] = f"{node}\n{body[:1200]}"
                break
    return out


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
    paths: list[str] | None = None,
    changed_only: bool = False,
) -> Evidence:
    repo = git_ops.repo_root(repo)
    head_sha = git_ops.resolve(head, cwd=repo)
    base_sha = git_ops.merge_base(base, head, cwd=repo)

    name = runner_name or runners.detect(repo) or "pytest"
    runner = runners.RUNNERS[name]
    notes: list[str] = []

    # Large suites take hours; the question is usually about the tests the
    # change touched. --paths restricts every run to those files;
    # --changed-only derives them from the diff. The cross-run uses the base
    # branch's copies, so a test file the PR deleted still runs there.
    if changed_only:
        changed = git_ops.changed_files(base_sha, head_sha, cwd=repo)
        test_globs = git_ops.DEFAULT_TEST_GLOBS
        paths = sorted({f for f in changed if any(git_ops.matches_glob(f, g) for g in test_globs)}) + list(paths or [])
        if not paths:
            notes.append("--changed-only: the change touches no test file; running the whole suite")
            paths = None
    if paths:
        notes.append(f"restricted to {len(paths)} path(s): " + ", ".join(paths[:4]) + (" …" if len(paths) > 4 else ""))

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
            # Only paths that exist in this tree: a test file the PR added
            # is absent from the base tree and vice versa.
            present = [p for p in (paths or []) if (rev_tree / p).exists()] or None
            return runners.run(
                runner, rev_tree, reports / f"{label}.xml", paths=present,
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

    changed = git_ops.changed_files(base_sha, head_sha, cwd=repo)
    changed_tests = {f for f in changed if any(git_ops.matches_glob(f, g) for g in git_ops.DEFAULT_TEST_GLOBS)}
    findings = compare(base_run, head_run, cross_run, changed_test_files=changed_tests,
                       assertion_diffs=_assertion_diffs(repo, base_sha, head_sha, base_run, cross_run, changed_tests))

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
        integrity.reconcile_with_run(cw_findings, findings)
        findings += cw_findings
        if note:
            notes.append(note)
        findings += integrity.drop_covered_by_checkwash(integrity.detect_js_gaps(repo, base_sha, head_sha), cw_findings)
        findings += coverage.detect_coverage_replaced(repo, base_sha, head_sha, changed)

    # Highest severity first, then by signal, so the report opens with the
    # thing most worth reading.
    order = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2, Severity.INFO: 3}
    findings.sort(key=lambda f: (order[f.severity], f.signal))

    checked = claims_mod.check(
        claims_mod.extract(claim_text), base_run, head_run, cross_run,
        restricted=bool(paths),
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
