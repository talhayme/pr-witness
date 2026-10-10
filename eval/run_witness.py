#!/usr/bin/env python3
"""Score pr-witness itself against the corpus.

Each case is turned into a two-commit git repository, exactly as a pull
request would appear, and pr-witness is run on it end to end — the real
worktrees, the real runners, the real comparison. Nothing here reads
measured.json: this measures the tool, not the fixture.
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

from pr_witness.compare import Severity  # noqa: E402
from pr_witness.witness import witness  # noqa: E402

# Signals that assert dishonesty. INFO-level findings (a documented skip)
# are recorded but do not constitute a flag.
FLAGGING = {Severity.HIGH, Severity.MEDIUM}


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
    only = sys.argv[1] if len(sys.argv) > 1 else None
    tsrunner = ROOT / ".tsrunner" / "node_modules"

    # Three truths, three verdicts. cheat must be flagged; review must be
    # surfaced as review (the run cannot tell an honest rewrite from a
    # dishonest one, so the tool's job is to show it, not to judge it);
    # clean must be left alone.
    from collections import Counter
    matrix = Counter(); rows = []
    tp = fp = tn = fn = 0

    cases = [p for p in sorted(CASES.iterdir()) if p.is_dir() and not (only and only not in p.name)]
    for case_path in cases:
        label_text = (case_path / "label.yaml").read_text(encoding="utf-8")
        truth = re.search(r"^verdict: (\w+)", label_text, re.M).group(1)
        language = re.search(r"^language: (\S+)", label_text, re.M).group(1)
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            make_repo(case_path, repo)
            if language == "typescript" and tsrunner.exists():
                (repo / "node_modules").symlink_to(tsrunner)
                (repo / "package.json").write_text(
                    json.dumps({"name": "case", "private": True, "type": "module"}),
                    encoding="utf-8",
                )
            body = case_path / "pr_body.md"
            try:
                ev = witness(repo=repo, base="HEAD~1", head="HEAD",
                             runner_name="vitest" if language == "typescript" else "pytest",
                             pr_body=body.read_text(encoding="utf-8") if body.exists() else "",
                             timeout=300)
                tool = {"flag": "flag", "review": "review"}.get(ev.verdict, "clean")
                detail = ", ".join(f.signal for f in ev.findings if f.severity in FLAGGING or f.signal == "expectation_changed")
                detail += "".join(f", claim_false({c.shown})" for c in ev.claims if c.verdict.value == "false")
            except Exception as exc:  # noqa: BLE001
                tool, detail = "error", f"error: {exc}"
        matrix[(truth, tool)] += 1
        expected = {"cheat": "flag"}.get(truth, truth)
        ok = (tool == expected)
        # the two-class numbers, for continuity with earlier phases:
        # anything not clean is "positive"; surfaced = flag or review.
        pos, surfaced = truth != "clean", tool != "clean"
        if pos and surfaced: tp += 1
        elif pos: fn += 1
        elif surfaced: fp += 1
        else: tn += 1
        sym = "✓" if ok else ("✗ missed" if pos and not surfaced else "✗ false alarm" if not pos and surfaced else "~ wrong level")
        rows.append((case_path.name, truth, tool, detail or "—"))
        print(f"  {sym:14} {case_path.name:38} truth={truth:7} tool={tool:7} {detail or '—'}")

    print("\n  truth \\ tool      flag  review  clean")
    for truth in ("cheat", "review", "clean"):
        print(f"  {truth:14}" + "".join(f"{matrix[(truth, v)]:>7}" for v in ("flag", "review", "clean")))
    exact = matrix[("cheat", "flag")] + matrix[("review", "review")] + matrix[("clean", "clean")]
    print(f"  exact verdict: {exact}/{len(cases)}")
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    print()
    print(f"  pr-witness   cases: {tp+fp+tn+fn}")
    print(f"  TP {tp}  FP {fp}  TN {tn}  FN {fn}")
    print(f"  precision {precision:.2f}   recall {recall:.2f}   F1 {f1:.2f}")

    out = ROOT / "eval" / "witness_results.md"
    lines = [
        "# Evaluation — pr-witness", "",
        "Three verdicts: cheat → flag, review → review, clean → clean. Two-class numbers (surfaced vs not) kept for continuity.", "",
        "| truth \\ tool | flag | review | clean |", "|---|---|---|---|",
        *[f"| {t} | " + " | ".join(str(matrix[(t, v)]) for v in ("flag", "review", "clean")) + " |" for t in ("cheat", "review", "clean")],
        f"Exact verdict: {exact}/{len(cases)}", "",
        f"Cases: {tp+fp+tn+fn}  ·  TP {tp}  FP {fp}  TN {tn}  FN {fn}", "",
        "| metric | value |", "|---|---|",
        f"| precision | {precision:.2f} |", f"| recall | {recall:.2f} |", f"| F1 | {f1:.2f} |",
        "", "| case | truth | tool | signals |", "|---|---|---|---|",
    ]
    lines += [f"| `{c}` | {t} | {o} | {d} |" for c, t, o, d in rows]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
