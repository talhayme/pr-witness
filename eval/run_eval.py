#!/usr/bin/env python3
"""Measure a tool against the corpus.

Reports precision, recall and F1 for the verdict (does the tool flag the
dishonest cases and leave the honest ones alone), plus a per-case table so a
disagreement can be read rather than guessed at.

Precision is the number that matters here. A tool that flags every change
catches all the cheating and is still useless, because the people reading its
output stop reading it.

Usage:
    python eval/run_eval.py --tool checkwash
    python eval/run_eval.py --tool crossrun     # the baseline our signals imply
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).parent.parent
CASES = ROOT / "corpus" / "cases"
sys.path.insert(0, str(ROOT / "src"))
from pr_witness.integrity import checkwash_command  # noqa: E402


@dataclass
class Case:
    id: str
    verdict: str
    language: str
    signals: list[str]
    path: Path

    @property
    def is_cheat(self) -> bool:
        return self.verdict == "cheat"


def load_cases() -> list[Case]:
    cases = []
    for d in sorted(p for p in CASES.iterdir() if p.is_dir()):
        label = (d / "label.yaml").read_text(encoding="utf-8")
        verdict = re.search(r"^verdict: (\w+)", label, re.M).group(1)
        language = re.search(r"^language: (\S+)", label, re.M).group(1)
        block = re.search(r"^signals:\n((?:  - \S+\n)*)", label, re.M)
        signals = re.findall(r"  - (\S+)", block.group(1)) if block else []
        cases.append(Case(d.name, verdict, language, signals, d))
    return cases


def git_diff(case: Case) -> str:
    """Produce a base→head diff the way a pull request would present it."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        env_args = ["-c", "user.email=e@x", "-c", "user.name=n"]

        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        shutil.copytree(case.path / "base", repo, dirs_exist_ok=True)
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", *env_args, "commit", "-qm", "base"], cwd=repo, check=True)

        for item in repo.iterdir():
            if item.name != ".git":
                shutil.rmtree(item) if item.is_dir() else item.unlink()
        shutil.copytree(case.path / "head", repo, dirs_exist_ok=True)
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", *env_args, "commit", "-qm", "head"], cwd=repo, check=True)

        out = subprocess.run(
            ["git", "diff", "HEAD~1..HEAD"], cwd=repo,
            capture_output=True, text=True, check=True,
        )
        return out.stdout


def run_checkwash(case: Case, bar: str = "verdict") -> tuple[bool, list[str]]:
    """Returns (flagged, detail).

    Two bars, because checkwash reports at two levels and only one of them
    stops a pull request:

      verdict  — checkwash's own gate ("block"). This is the honest
                 comparison: it is what a team running checkwash in CI
                 actually experiences.
      any      — any finding at all, including advisory `warn`. Harsher than
                 the tool claims for itself, but it shows what a reviewer
                 skimming the full output would have to triage.
    """
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        env_args = ["-c", "user.email=e@x", "-c", "user.name=n"]
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        shutil.copytree(case.path / "base", repo, dirs_exist_ok=True)
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", *env_args, "commit", "-qm", "base"], cwd=repo, check=True)
        base_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                                  capture_output=True, text=True).stdout.strip()

        for item in repo.iterdir():
            if item.name != ".git":
                shutil.rmtree(item) if item.is_dir() else item.unlink()
        shutil.copytree(case.path / "head", repo, dirs_exist_ok=True)
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", *env_args, "commit", "-qm", "head"], cwd=repo, check=True)

        proc = subprocess.run(
            [*(checkwash_command() or ["checkwash"]), "check", f"{base_sha}..HEAD", "--format", "json"],
            cwd=repo, capture_output=True, text=True, timeout=180,
        )
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return False, []

        findings = data.get("findings") or []
        verdict = data.get("verdict", "pass")
        summary = data.get("summary", {})

        blocking = sorted({
            f.get("rule", "?") for f in findings
            if f.get("severity") in ("high", "critical")
        })
        all_rules = sorted({f.get("rule", "?") for f in findings})

        sev = " ".join(f"{k[0]}{v}" for k, v in sorted(summary.items()) if v)
        if bar == "verdict":
            detail = [f"verdict={verdict}"] + blocking
            return verdict == "block", detail + ([sev] if sev else [])
        return bool(all_rules), [f"verdict={verdict}"] + all_rules + ([sev] if sev else [])


def run_crossrun(case: Case) -> tuple[bool, list[str]]:
    """The baseline pr-witness implies: measured counts and the cross-run.

    This is not the tool — it is the signal the corpus was built around,
    computed directly from corpus/measured.json, so phase 0 can report what
    these signals are worth before any of the tool exists.
    """
    measured = json.loads((ROOT / "corpus" / "measured.json").read_text(encoding="utf-8"))
    m = measured.get(case.id)
    if m is None:
        return False, []

    base, head, cross = m["base"], m["head"], m["crossrun"]
    signals = []

    # A base test failing on the new code. Collection errors are excluded:
    # an import error after a feature is deliberately removed is expected,
    # and counting it would flag the honest removal case.
    if cross["failed"] > 0:
        signals.append("crossrun")
    if head["collected"] < base["collected"]:
        signals.append("denominator")
    if head["skipped"] > base["skipped"]:
        signals.append("skip_inflation")

    return bool(signals), signals


TOOLS = {
    "checkwash": run_checkwash,                                  # its own gate
    "checkwash-any": lambda c: run_checkwash(c, bar="any"),      # every finding
    "crossrun": run_crossrun,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", choices=sorted(TOOLS), required=True)
    ap.add_argument("--out", type=Path, default=ROOT / "eval" / "results.md")
    args = ap.parse_args()

    runner = TOOLS[args.tool]
    cases = load_cases()
    if args.tool == "crossrun":
        # Counts are measured per language: verify.py for Python, verify_ts.py
        # for TypeScript. A case with no entry in measured.json is skipped
        # rather than silently scored as "not flagged".
        measured = json.loads((ROOT / "corpus" / "measured.json").read_text(encoding="utf-8"))
        missing = [c.id for c in cases if c.id not in measured]
        if missing:
            print(f"  not measured, skipping: {', '.join(missing)}", file=sys.stderr)
        cases = [c for c in cases if c.id in measured]

    tp = fp = tn = fn = 0
    rows = []

    for case in cases:
        try:
            flagged, detail = runner(case)
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR {case.id}: {exc}", file=sys.stderr)
            flagged, detail = False, [f"error: {exc}"]

        if case.is_cheat and flagged:
            outcome, sym = "TP", "✓"
            tp += 1
        elif case.is_cheat and not flagged:
            outcome, sym = "FN", "✗ missed"
            fn += 1
        elif not case.is_cheat and flagged:
            outcome, sym = "FP", "✗ false alarm"
            fp += 1
        else:
            outcome, sym = "TN", "✓"
            tn += 1

        rows.append((case.id, case.verdict, outcome, ", ".join(detail) or "—"))
        print(f"  {sym:14} {case.id:38} {', '.join(detail) or '—'}")

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    print()
    print(f"  tool: {args.tool}   cases: {len(cases)}")
    print(f"  TP {tp}  FP {fp}  TN {tn}  FN {fn}")
    print(f"  precision {precision:.2f}   recall {recall:.2f}   F1 {f1:.2f}")
    print()

    lines = [
        f"# Evaluation — {args.tool}",
        "",
        f"Cases: {len(cases)}  ·  TP {tp}  FP {fp}  TN {tn}  FN {fn}",
        "",
        f"| metric | value |",
        f"|---|---|",
        f"| precision | {precision:.2f} |",
        f"| recall | {recall:.2f} |",
        f"| F1 | {f1:.2f} |",
        "",
        "| case | truth | outcome | detail |",
        "|---|---|---|---|",
    ]
    for cid, truth, outcome, detail in rows:
        lines.append(f"| `{cid}` | {truth} | {outcome} | {detail} |")
    lines.append("")

    existing = args.out.read_text(encoding="utf-8") if args.out.exists() else ""
    marker = f"# Evaluation — {args.tool}"
    if marker in existing:
        head, _, rest = existing.partition(marker)
        _, _, after = rest.partition("\n# Evaluation — ")
        existing = head + ("\n# Evaluation — " + after if after else "")
    args.out.write_text((existing.rstrip() + "\n\n" if existing.strip() else "")
                        + "\n".join(lines), encoding="utf-8")
    print(f"  written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
