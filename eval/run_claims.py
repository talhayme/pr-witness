#!/usr/bin/env python3
"""Score claim checking against the verdicts the corpus labels declare.

Each label.yaml carries the claims in its pr_body.md and the right answer
for each. This compares what the checker decided against what a human said
was true, case by case.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
CASES = ROOT / "corpus" / "cases"
sys.path.insert(0, str(ROOT / "src"))

from pr_witness.witness import witness  # noqa: E402


def labelled_claims(label: str) -> list[tuple[str, str]]:
    """(text, verdict) pairs from a label.yaml claims: block."""
    block = re.search(r"^claims:\n((?:  - .*\n(?:    .*\n)*)*)", label, re.M)
    if not block:
        return []
    out = []
    for item in re.finditer(
        r"- text: ['\"](.+?)['\"]\s*\n\s*verdict: (\w+)", block.group(1)
    ):
        out.append((item.group(1), item.group(2)))
    return out


def make_repo(case: Path, dest: Path) -> None:
    ident = ["-c", "user.email=e@x", "-c", "user.name=n"]
    subprocess.run(["git", "init", "-q", str(dest)], check=True)
    for side in ("base", "head"):
        for item in dest.iterdir():
            if item.name != ".git":
                shutil.rmtree(item) if item.is_dir() else item.unlink()
        shutil.copytree(case / side, dest, dirs_exist_ok=True)
        subprocess.run(["git", "add", "-A"], cwd=dest, check=True)
        subprocess.run(["git", *ident, "commit", "-qm", side], cwd=dest, check=True)


def main() -> int:
    tsrunner = ROOT / ".tsrunner" / "node_modules"
    agree = disagree = unlabelled = 0
    rows = []

    for case in sorted(p for p in CASES.iterdir() if p.is_dir()):
        label = (case / "label.yaml").read_text(encoding="utf-8")
        language = re.search(r"^language: (\S+)", label, re.M).group(1)
        body_file = case / "pr_body.md"
        if not body_file.exists():
            continue
        expected = labelled_claims(label)

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            make_repo(case, repo)
            if language == "typescript" and tsrunner.exists():
                (repo / "node_modules").symlink_to(tsrunner)
                (repo / "package.json").write_text(
                    json.dumps({"name": "c", "private": True, "type": "module"}),
                    encoding="utf-8")
            ev = witness(repo=repo, base="HEAD~1", head="HEAD",
                         runner_name="vitest" if language == "typescript" else "pytest",
                         pr_body=body_file.read_text(encoding="utf-8"),
                         skip_integrity=True, timeout=300)

        got = [(c.shown, c.verdict.value, c.because) for c in ev.claims]
        print(f"  {case.name}")
        if not got:
            print("      (no claims extracted)")
        for shown, verdict, because in got:
            # Match a labelled claim by overlap: the label quotes the
            # author's words, the checker quotes the matched fragment.
            match = next(
                (v for text, v in expected
                 if shown.lower() in text.lower() or text.lower() in shown.lower()),
                None,
            )
            if match is None:
                mark, unlabelled = "·", unlabelled + 1
            elif match == verdict:
                mark, agree = "✓", agree + 1
            else:
                mark, disagree = "✗", disagree + 1
            suffix = f"  (label says {match})" if match and match != verdict else ""
            print(f"      {mark} {verdict:13} \"{shown}\"{suffix}")
            if mark == "✗":
                print(f"              because: {because}")
            rows.append((case.name, shown, verdict, match or "—"))

    total = agree + disagree
    print()
    print(f"  labelled claims: {total}   agree {agree}   disagree {disagree}")
    if total:
        print(f"  agreement: {agree / total:.2f}")
    print(f"  extracted but not labelled: {unlabelled}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
