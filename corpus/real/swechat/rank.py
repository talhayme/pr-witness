#!/usr/bin/env python3
"""Step 3: a reading order for the candidates, from the test-side diff.

Ranking is not a label. It puts the commits most worth a human's eyes first:
assertions removed, skip markers added, expected values changed, tests
deleted outright. Labels are given by hand after reading the diff and, where
it helps, the session transcript.

    python rank.py <dir>   → <dir>/candidates.json, ranked
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ASSERTION = re.compile(r"\b(assert\w*|expect|should|raises|toBe|toEqual|toStrictEqual|strictEqual|deepEqual)\b")
# Framework markers only. The bare words skip/todo/only are data in half the
# test suites in the world (`status: 'todo'`), which is how a first version
# of this counted 558 "skips added" that were mostly nothing.
SKIP = re.compile(r"(pytest\.mark\.(skip|skipif|xfail)|pytest\.(skip|xfail)\(|@unittest\.(skip|skipIf|skipUnless|expectedFailure)"
                  r"|\b(it|test|describe|suite)\.(skip|todo|only|fixme)\(|\b(xit|xtest|xdescribe|fit|fdescribe)\(|\bt\.Skip(f|Now)?\("
                  r"|#\[ignore\]|@Ignore\b|@Disabled\b|\.skip\s*$)")
EXPECTED = re.compile(r"(toBe|toEqual|assertEqual|assertEquals|assert\s+\w+\s*==|==\s*|expect\()")


def score(patch: str) -> dict:
    removed = [l[1:] for l in patch.splitlines() if l.startswith("-") and not l.startswith("---")]
    added = [l[1:] for l in patch.splitlines() if l.startswith("+") and not l.startswith("+++")]
    s = {
        "assertions_removed": sum(bool(ASSERTION.search(l)) for l in removed),
        "assertions_added": sum(bool(ASSERTION.search(l)) for l in added),
        "skips_added": sum(bool(SKIP.search(l)) for l in added) - sum(bool(SKIP.search(l)) for l in removed),
        "expected_changed": min(sum(bool(EXPECTED.search(l)) for l in removed), sum(bool(EXPECTED.search(l)) for l in added)),
        "test_lines_removed": len(removed), "test_lines_added": len(added),
    }
    net_assert_loss = max(s["assertions_removed"] - s["assertions_added"], 0)
    s["rank"] = 4 * net_assert_loss + 4 * max(s["skips_added"], 0) + 2 * s["expected_changed"] + max(len(removed) - len(added), 0) // 10
    return s


def main(data: Path) -> int:
    cands = json.loads((data / "candidates_light.json").read_text(encoding="utf-8"))
    out = []
    for c in cands:
        f = data / "diffs" / f"{c['sha']}.json"
        if not f.exists():
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        if "error" in d:
            continue
        test_files = {x["filename"]: x for x in d["files"] if x["filename"] in c["test_files"]}
        # Only tests that already existed can be weakened. A new test file
        # full of `it.todo` is scaffolding, not a hidden test; a deleted one
        # is the strongest signal there is.
        modified = [x for x in test_files.values() if x["status"] == "modified" and x.get("patch")]
        added = [x for x in test_files.values() if x["status"] == "added"]
        deleted = [x["filename"] for x in test_files.values() if x["status"] == "removed"]
        s = score("\n".join(x["patch"] for x in modified)) if modified else score("")
        churn = s["test_lines_removed"] + s["test_lines_added"]
        # Balanced mass rewrites (a formatter, a rename) score high on every
        # count and mean nothing; scale the rewrite signal by imbalance.
        imbalance = (s["test_lines_removed"] - s["test_lines_added"]) / churn if churn else 0.0
        s["rank"] = (4 * max(s["assertions_removed"] - s["assertions_added"], 0)
                     + 4 * max(s["skips_added"], 0)
                     + round(2 * s["expected_changed"] * max(imbalance, 0.1))
                     + 8 * len(deleted))
        out.append({**c, "parent": d["parents"][0] if d["parents"] else None,
                    "tests_modified": [x["filename"] for x in modified], "tests_added": [x["filename"] for x in added],
                    "deleted_tests": deleted, **s})
    out.sort(key=lambda c: -c["rank"])
    (data / "candidates.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"{len(out)} ranked; rank>0: {sum(c['rank'] > 0 for c in out)}; net assertions removed from existing tests: "
          f"{sum(c['assertions_removed'] > c['assertions_added'] for c in out)}; skips added to existing tests: "
          f"{sum(c['skips_added'] > 0 for c in out)}; test files deleted: {sum(bool(c['deleted_tests']) for c in out)}")
    for c in out[:30]:
        print(f"  {c['rank']:3} {c['repo']:34} {c['sha'][:8]} -A{c['assertions_removed']} +A{c['assertions_added']} skip{c['skips_added']:+} exp{c['expected_changed']} del{len(c['deleted_tests'])} mod{len(c['tests_modified'])} | {c['message'][:55]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
