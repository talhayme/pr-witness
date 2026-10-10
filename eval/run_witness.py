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

    tp = fp = tn = fn = 0
    rows = []

    for case in sorted(p for p in CASES.iterdir() if p.is_dir()):
        if only and only not in case.name:
            continue
        label = (case / "label.yaml").read_text(encoding="utf-8")
        is_cheat = "verdict: cheat" in label
        language = re.search(r"^language: (\S+)", label, re.M).group(1)

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            make_repo(case, repo)
            if language == "typescript" and tsrunner.exists():
                (repo / "node_modules").symlink_to(tsrunner)
                (repo / "package.json").write_text(
                    json.dumps({"name": "case", "private": True, "type": "module"}),
                    encoding="utf-8",
                )

            try:
                ev = witness(repo=repo, base="HEAD~1", head="HEAD",
                             runner_name="vitest" if language == "typescript" else "pytest",
                             timeout=300)
                signals = [f.signal for f in ev.findings if f.severity in FLAGGING]
                info = [f.signal for f in ev.findings if f.severity not in FLAGGING]
            except Exception as exc:  # noqa: BLE001
                print(f"  ERROR {case.name}: {exc}", file=sys.stderr)
                signals, info = [], [f"error: {exc}"]

        flagged = bool(signals)
        if is_cheat and flagged:
            outcome, sym = "TP", "✓"; tp += 1
        elif is_cheat:
            outcome, sym = "FN", "✗ missed"; fn += 1
        elif flagged:
            outcome, sym = "FP", "✗ false alarm"; fp += 1
        else:
            outcome, sym = "TN", "✓"; tn += 1

        detail = ", ".join(signals + [f"({i})" for i in info]) or "—"
        rows.append((case.name, "cheat" if is_cheat else "clean", outcome, detail))
        print(f"  {sym:14} {case.name:38} {detail}")

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    print()
    print(f"  pr-witness   cases: {tp+fp+tn+fn}")
    print(f"  TP {tp}  FP {fp}  TN {tn}  FN {fn}")
    print(f"  precision {precision:.2f}   recall {recall:.2f}   F1 {f1:.2f}")

    out = ROOT / "eval" / "witness_results.md"
    lines = [
        "# Evaluation — pr-witness (phase 1)", "",
        f"Cases: {tp+fp+tn+fn}  ·  TP {tp}  FP {fp}  TN {tn}  FN {fn}", "",
        "| metric | value |", "|---|---|",
        f"| precision | {precision:.2f} |", f"| recall | {recall:.2f} |", f"| F1 | {f1:.2f} |",
        "", "| case | truth | outcome | signals |", "|---|---|---|---|",
    ]
    lines += [f"| `{c}` | {t} | {o} | {d} |" for c, t, o, d in rows]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
