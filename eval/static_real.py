#!/usr/bin/env python3
"""Run the static replacement detector on every real case, installing nothing.

`coverage_replaced` reads source; it needs two snapshots of a repository and
no test run. This fetches exactly those two commits (depth 1, blobs under
2 MB) and reads them — no checkout, no dependencies, none of the project's
code executed — so it is cheap enough to ask of every real case whenever
the detector changes: does it fire where the label says nothing should?

    python eval/static_real.py [--source swechat|swebench] [case …]
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from pr_witness import coverage, git_ops  # noqa: E402
from run_real import label  # noqa: E402

CACHE = Path(os.environ.get("PR_WITNESS_REAL_CACHE", Path.home() / ".cache" / "pr-witness-real")) / "static"


def git(*args, cwd, check=True):
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=1800)
    if check and p.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {p.stderr.strip()[-300:]}")
    return p.stdout.strip()


def snapshots(case: Path, lab: dict) -> tuple[Path, str, str]:
    d = CACHE / case.name
    base, head = lab["base_commit"], lab.get("head_commit")
    if not (d / ".git").exists():
        d.mkdir(parents=True, exist_ok=True)
        git("init", "-q", cwd=d)
        git("remote", "add", "origin", f"https://github.com/{lab['repo']}.git", cwd=d)
        git("fetch", "-q", "--depth", "1", "--filter=blob:limit=2m", "origin", base, *([head] if head else []), cwd=d)
    if head:
        return d, base, head
    # SWE-bench: the head is the agent's patch on top of the base. Built in
    # the index — nothing is checked out.
    git("read-tree", base, cwd=d)
    git("apply", "--cached", str(case / "agent.diff"), cwd=d)
    tree = git("write-tree", "--missing-ok", cwd=d)
    head = git("-c", "user.name=agent", "-c", "user.email=e@x", "commit-tree", tree, "-p", base, "-m", "agent patch", cwd=d)
    return d, base, head


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cases", nargs="*")
    ap.add_argument("--source", action="append")
    args = ap.parse_args()
    fired = 0
    for source in args.source or ["swebench", "swechat"]:
        root = ROOT / "corpus" / "real" / source / "cases"
        for case in sorted(p for p in root.iterdir() if p.is_dir()):
            if args.cases and case.name not in args.cases:
                continue
            lab = label(case)
            if lab.get("language", "python") != "python":
                print(f"  –  {source}/{case.name:34} not Python")
                continue
            try:
                d, base, head = snapshots(case, lab)
                found = coverage.detect_coverage_replaced(d, base, head, git_ops.changed_files(base, head, cwd=d))
            except Exception as exc:  # noqa: BLE001
                print(f"  !  {source}/{case.name:34} {str(exc).splitlines()[-1][:120]}")
                continue
            fired += bool(found)
            print(f"  {'●' if found else '·'}  {source}/{case.name:34} label={lab.get('verdict'):7} "
                  + (found[0].summary[:150] if found else "nothing"))
    print(f"coverage_replaced fired on {fired} case(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
