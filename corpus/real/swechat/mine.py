#!/usr/bin/env python3
"""Find candidate test edits in SWE-chat (SALT-NLP/SWE-chat, ODC-BY).

SWE-chat publishes real Claude Code sessions on real repositories with the
commits they produced — `commits.parquet` has the full unified diff of each
commit and which files the agent touched. Unlike SWE-bench there is no
official test patch to label against, so a candidate here is a commit that

  * is attributed to the agent (`is_agent_author`, or an agent-only test
    file in `file_attribution`),
  * touches at least one test file *and* at least one non-test file —
    without a code change there is nothing for the cross-run to run against,
  * comes from a repository whose licence the dataset marks usable.

Candidates are ranked by what the test-side diff does: removed assertions,
added skip markers, changed expected values. Ranking is a reading order for
a human, not a label. Labels are given by hand after reading the diff and,
where it helps, the session transcript.

    python mine.py <dir with commits.parquet + repositories.parquet>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pyarrow.parquet as pq

TEST_PATH = re.compile(r"(^|/)(tests?|__tests__|spec)/|(^|/)test_[^/]+\.py$|_test\.(py|go)$|\.(test|spec)\.[cm]?[jt]sx?$|Tests?\.(cs|java|kt)$")
ASSERTION = re.compile(r"\b(assert\w*|expect|should|raises|toBe|toEqual|strictEqual)\b")
SKIP = re.compile(r"\b(skip|xfail|only|todo|pytest\.mark\.skip|@unittest\.skip|it\.skip|describe\.skip|t\.Skip)\b")


def split_patch(patch: str) -> dict[str, list[str]]:
    """file path → its diff lines (added/removed only)."""
    files: dict[str, list[str]] = {}
    current = None
    for line in patch.splitlines():
        if line.startswith("+++ "):
            current = line[4:].strip()
            current = current[2:] if current.startswith("b/") else current
            files.setdefault(current, [])
        elif current and line[:1] in "+-" and not line.startswith(("+++", "---")):
            files[current].append(line)
    return files


def score(test_lines: list[str]) -> dict:
    removed = [l[1:] for l in test_lines if l[0] == "-"]
    added = [l[1:] for l in test_lines if l[0] == "+"]
    return {
        "assertions_removed": sum(bool(ASSERTION.search(l)) for l in removed),
        "assertions_added": sum(bool(ASSERTION.search(l)) for l in added),
        "skips_added": sum(bool(SKIP.search(l)) for l in added) - sum(bool(SKIP.search(l)) for l in removed),
        "test_lines_removed": len(removed),
        "test_lines_added": len(added),
    }


def main(data: Path) -> int:
    repos = pq.read_table(data / "repositories.parquet", columns=["repo_id", "url", "license_type", "is_fork"]).to_pylist()
    usable = {r["repo_id"]: r for r in repos if r["license_type"] and r["license_type"].lower() not in ("unknown", "none", "unusable", "no_license")}
    print(f"repositories: {len(repos)}, with a usable licence: {len(usable)}", file=sys.stderr)

    pf = pq.ParquetFile(data / "commits.parquet")
    cols = ["commit_sha", "repo_id", "status", "is_agent_author", "files_changed", "file_attribution",
            "total_additions", "total_deletions", "commit_message", "patch"]
    out, seen, scanned = [], set(), 0
    for batch in pf.iter_batches(batch_size=512, columns=cols):
        for row in batch.to_pylist():
            scanned += 1
            if row["status"] != "ok" or not row["commit_sha"] or row["repo_id"] not in usable:
                continue
            if row["commit_sha"] in seen:
                continue
            files = split_patch(row["patch"] or "")
            tests = [f for f in files if TEST_PATH.search(f)]
            code = [f for f in files if not TEST_PATH.search(f)]
            if not tests or not code:
                continue
            attribution = json.loads(row["file_attribution"] or "{}") if isinstance(row["file_attribution"], str) else (row["file_attribution"] or {})
            agent_test = any(attribution.get(f) in ("agent_only", "mixed") for f in tests)
            if not (row["is_agent_author"] or agent_test):
                continue
            seen.add(row["commit_sha"])
            s = score([l for f in tests for l in files[f]])
            s["rank"] = 3 * s["assertions_removed"] + 4 * max(s["skips_added"], 0) + max(s["test_lines_removed"] - s["test_lines_added"], 0) // 5
            out.append({
                "repo": row["repo_id"], "url": usable[row["repo_id"]]["url"], "license": usable[row["repo_id"]]["license_type"],
                "sha": row["commit_sha"], "message": (row["commit_message"] or "").splitlines()[0][:120],
                "test_files": tests, "code_files": code[:10], "attribution": {f: attribution.get(f) for f in tests},
                "agent_author": bool(row["is_agent_author"]), **s,
            })
        if scanned % 8192 == 0:
            print(f"  scanned {scanned}, candidates {len(out)}", file=sys.stderr)
    out.sort(key=lambda c: -c["rank"])
    (data / "candidates.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"scanned {scanned} commit rows → {len(out)} candidates (agent-attributed, test + code files, usable licence)")
    print(f"  with assertions removed: {sum(c['assertions_removed'] > 0 for c in out)}")
    print(f"  with skips added:        {sum(c['skips_added'] > 0 for c in out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
