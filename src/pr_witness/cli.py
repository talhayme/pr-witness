"""pr-witness command line."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pr_witness import __version__, render
from pr_witness.compare import Severity
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
    ap.add_argument("--runner", choices=["pytest", "vitest", "jest", "go"],
                    help="override runner detection")
    ap.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    ap.add_argument("--no-crossrun", action="store_true",
                    help="skip the base-tests-on-head-code run")
    ap.add_argument("--no-integrity", action="store_true",
                    help="skip the diff-level checks (checkwash and the JS/TS gaps)")
    ap.add_argument("--pr-body", type=Path,
                    help="file holding the pull request description; without it, "
                         "claims are read from the commit messages")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--keep-reports", type=Path,
                    help="write the three JUnit reports here instead of discarding them")
    ap.add_argument(
        "--fail-on", choices=["never", "high", "medium"], default="never",
        help="exit non-zero on findings at this severity or above "
             "(default: never — pr-witness reports, it does not block)",
    )
    args = ap.parse_args(argv)

    ev = witness(
        repo=args.repo, base=args.base, head=args.head,
        runner_name=args.runner, skip_crossrun=args.no_crossrun,
        skip_integrity=args.no_integrity,
        pr_body=args.pr_body.read_text(encoding='utf-8') if args.pr_body else '',
        timeout=args.timeout, keep_reports=args.keep_reports,
    )

    if args.format == "json":
        print(json.dumps(ev.as_dict(), indent=2))
    elif args.format == "markdown":
        print(render.to_markdown(ev), end="")
    else:
        print(render.to_text(ev), end="")

    if args.fail_on == "never":
        return 0
    # A disproved claim fails at any bar: it is the clearest statement the
    # tool can make, and the hardest to dismiss as a heuristic.
    if any(c.verdict.value == "false" for c in ev.claims):
        return 1
    bar = {Severity.HIGH} if args.fail_on == "high" else {Severity.HIGH, Severity.MEDIUM}
    return 1 if any(f.severity in bar for f in ev.findings) else 0


if __name__ == "__main__":
    sys.exit(main())
