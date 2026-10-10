#!/usr/bin/env python3
"""Which agent patches on SWE-bench Verified touch test files, and did they resolve?

Step A of building a real-case corpus. SWE-bench's own harness overwrites
the agent's test edits with the official test patch before grading, so
editing tests cannot cheat *SWE-bench* — but it tells us where agents
reach for the tests at all, and those patches are the candidates for a
cross-run on the real repository.
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent
meta = {r["instance_id"]: r for r in json.load(open("/tmp/w/swebench_verified.json"))}
TEST_PATH = re.compile(r"(^|/)(tests?|testing)/(?!testcases\.py|runner\.py|utils\.py)|(^|/)test_[^/]+\.py$|_test\.py$|(^|/)conftest\.py$")


def files_in(diff: str) -> list[str]:
    return re.findall(r"^diff --git a/(\S+) b/", diff, re.M)


def main() -> None:
    rows = []
    for sub in sorted((HERE / "patches").iterdir()):
        # Prefer the harness's per-instance report.json; per_instance_details
        # is wrong for at least one submission (all False, metadata says 69.6%).
        details = {}
        rdir = HERE / "reports" / sub.name
        if rdir.exists():
            for rf in rdir.glob("*.json"):
                try:
                    rep = json.load(open(rf))
                    inner = rep.get(rf.stem, rep)
                    details[rf.stem] = {"resolved": bool(inner.get("resolved"))}
                except Exception:  # noqa: BLE001
                    pass
        if not details:
            dp = HERE / f"details_{sub.name}.json"
            if dp.exists():
                details = json.load(open(dp))
        n = touch = touch_resolved = empty = 0
        by_repo = Counter(); touched_ids = []
        for f in sorted(sub.glob("*.diff")):
            iid = f.stem; diff = f.read_text(encoding="utf-8", errors="replace")
            n += 1
            if not diff.strip():
                empty += 1; continue
            tests = [p for p in files_in(diff) if TEST_PATH.search(p)]
            if tests:
                touch += 1; by_repo[meta[iid]["repo"]] += 1; touched_ids.append(iid)
                if details.get(iid, {}).get("resolved"):
                    touch_resolved += 1
        rows.append((sub.name, n, empty, touch, touch_resolved, by_repo, touched_ids))

    print(f"{'submission':46} {'patches':>8} {'empty':>6} {'touch tests':>12} {'…and resolved':>14}")
    for name, n, empty, touch, tr, by_repo, ids in rows:
        print(f"{name:46} {n:>8} {empty:>6} {touch:>7} ({100*touch/max(1,n):.1f}%) {tr:>10}")
    print("\nrepos of test-touching patches:")
    agg = Counter()
    for *_, by_repo, _ in rows: agg.update(by_repo)
    for repo, k in agg.most_common(): print(f"  {repo:28} {k}")

    light = {"pytest-dev/pytest", "pylint-dev/pylint", "psf/requests", "pallets/flask", "sphinx-doc/sphinx", "mwaskom/seaborn"}
    cands = defaultdict(set)
    for name, *_, ids in rows:
        for iid in ids:
            if meta[iid]["repo"] in light: cands[iid].add(name)
    print(f"\ncandidates in repos we can run locally: {len(cands)}")
    for iid, subs in sorted(cands.items()): print(f"  {iid:40} {len(subs)} submission(s)")
    json.dump({iid: sorted(s) for iid, s in cands.items()}, open(HERE / "candidates.json", "w"), indent=1)


if __name__ == "__main__":
    main()
