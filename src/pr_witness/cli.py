"""pr-witness command line."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pr_witness import __version__, render
from pr_witness.compare import Severity
from pr_witness.gate import APPROVAL_LABEL, MODES, decide
from pr_witness.witness import witness


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="pr-witness",
        description="Check whether a pull request's tests still mean what they meant.",
    )
    ap.add_argument("--version", action="version", version=__version__)
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument("--base", default="origin/main",
                    help="base revision (default: origin/main)")
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--runner", choices=["pytest", "vitest", "jest", "go", "django"],
                    help="override runner detection")
    ap.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    ap.add_argument("--no-crossrun", action="store_true",
                    help="skip the base-tests-on-head-code run")
    ap.add_argument("--no-integrity", action="store_true",
                    help="skip the diff-level checks (checkwash and the JS/TS gaps)")
    ap.add_argument("--pr-body", type=Path,
                    help="file holding the pull request description; without it, "
                         "claims are read from the commit messages")
    ap.add_argument("--paths", nargs="+", metavar="PATH",
                    help="run only these test files/directories (relative to the repo) in every run")
    ap.add_argument("--changed-only", action="store_true",
                    help="run only the test files the change touches (plus --paths)")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--keep-reports", type=Path,
                    help="write the three JUnit reports here instead of discarding them")
    ap.add_argument(
        "--mode", choices=MODES, default="report",
        help="report: never fail (default). require-ack: fail on a flag until "
             f"`{APPROVAL_LABEL}` is applied. strict: fail on a flag regardless",
    )
    ap.add_argument("--approved", action="store_true",
                    help=f"the `{APPROVAL_LABEL}` label is present on the pull request")
    ap.add_argument("--output", type=Path,
                    help="also write the rendered report to this file")
    ap.add_argument("--evidence", type=Path,
                    help="also write the evidence JSON (schema pr-witness/evidence/v1) here")
    ap.add_argument(
        "--fail-on", choices=["never", "high", "medium"], default=None,
        help="(legacy) exit non-zero on findings at this severity; prefer --mode",
    )
    args = ap.parse_args(argv)

    ev = witness(
        repo=args.repo, base=args.base, head=args.head,
        runner_name=args.runner, skip_crossrun=args.no_crossrun,
        skip_integrity=args.no_integrity,
        pr_body=args.pr_body.read_text(encoding='utf-8') if args.pr_body else '',
        timeout=args.timeout, keep_reports=args.keep_reports,
        paths=args.paths, changed_only=args.changed_only,
    )

    decision = decide(ev, args.mode, approved=args.approved)

    def evidence_json() -> str:
        payload = ev.as_dict()
        payload["gate"] = {"mode": args.mode, "exit_code": decision.exit_code,
                           "reason": decision.reason}
        return json.dumps(payload, indent=2) + "\n"

    if args.format == "json":
        rendered = evidence_json()
    elif args.format == "markdown":
        rendered = render.to_markdown(ev)
    else:
        rendered = render.to_text(ev)
        if args.mode != "report":
            rendered += f"\n  gate ({args.mode}): {decision.reason}\n"

    print(rendered, end="")
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(evidence_json(), encoding="utf-8")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")

    if args.fail_on is not None:
        # Legacy switch, kept so early users' pipelines do not break.
        if any(c.verdict.value == "false" for c in ev.claims):
            return 1
        if args.fail_on == "never":
            return 0
        bar = {Severity.HIGH} if args.fail_on == "high" else {Severity.HIGH, Severity.MEDIUM}
        return 1 if any(f.severity in bar for f in ev.findings) else 0

    return decision.exit_code

if __name__ == "__main__":
    sys.exit(main())
