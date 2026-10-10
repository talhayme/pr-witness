#!/usr/bin/env python3
"""Step 2: the test-side diff of each candidate commit, from GitHub, not from
the 5 GB file.

Candidates (from commits_light.parquet): status ok, an open-source licence,
at least one test file and one non-test file changed, and a test file the
agent wrote alone or together with the human. One API call per commit
(`GET /repos/{o}/{r}/commits/{sha}`), resumable, ~4,000 calls against a
5,000/hour budget; only the test files' patches and the code files' names
are kept. Nothing is written to anyone's repository.

    python fetch_diffs.py <dir with commits_light.parquet + repositories.parquet>
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

import pyarrow.parquet as pq

TEST_PATH = re.compile(r"(^|/)(tests?|__tests__|spec)/|(^|/)test_[^/]+\.py$|_test\.(py|go)$|\.(test|spec)\.[cm]?[jt]sx?$|Tests?\.(cs|java|kt)$")
OPEN_SOURCE = {"mit", "mit-0", "apache-2.0", "bsd-2-clause", "bsd-3-clause", "isc", "gpl-3.0", "gpl-2.0",
               "agpl-3.0", "agplv3", "lgpl-3.0", "lgpl-2.1", "mpl-2.0", "cc0 1.0 universal", "unlicense", "0bsd"}


def candidates(data: Path) -> list[dict]:
    repos = {r["repo_id"]: r for r in pq.read_table(data / "repositories.parquet", columns=["repo_id", "license_type", "url"]).to_pylist()}
    out, seen = [], set()
    for r in pq.read_table(data / "commits_light.parquet").to_pylist():
        if r["status"] != "ok" or not r["commit_sha"] or r["commit_sha"] in seen:
            continue
        repo = repos.get(r["repo_id"])
        if not repo or (repo["license_type"] or "").lower() not in OPEN_SOURCE:
            continue
        names = [l.split("\t")[-1] for l in (r["files_changed"] or "").splitlines() if l.strip()]
        tests = [f for f in names if TEST_PATH.search(f)]
        code = [f for f in names if not TEST_PATH.search(f)]
        if not tests or not code:
            continue
        labels = json.loads(r["attribution_labels"]) if r["attribution_labels"] else {}
        if not any(labels.get(f) in ("agent_only", "mixed") for f in tests):
            continue
        seen.add(r["commit_sha"])
        out.append({"repo": r["repo_id"], "sha": r["commit_sha"], "license": repo["license_type"],
                    "message": (r["commit_message"] or "").splitlines()[0][:120] if r["commit_message"] else "",
                    "test_files": tests, "code_files": code, "attribution": {f: labels.get(f) for f in tests},
                    "additions": r["total_additions"], "deletions": r["total_deletions"]})
    return out


def main(data: Path) -> int:
    cands = candidates(data)
    (data / "candidates_light.json").write_text(json.dumps(cands, indent=1), encoding="utf-8")
    diffs = data / "diffs"; diffs.mkdir(exist_ok=True)
    todo = [c for c in cands if not (diffs / f"{c['sha']}.json").exists()]
    print(f"{len(cands)} candidates, {len(todo)} to fetch", flush=True)
    failed = 0
    for i, c in enumerate(todo):
        p = subprocess.run(["gh", "api", f"repos/{c['repo']}/commits/{c['sha']}"], capture_output=True, text=True)
        if p.returncode:
            err = p.stderr.strip()[-200:]
            if "rate limit" in err.lower() or "403" in err:
                print(f"  rate limited at {i}; sleeping 15 min", flush=True); time.sleep(900); continue
            (diffs / f"{c['sha']}.json").write_text(json.dumps({"error": err}), encoding="utf-8")
            failed += 1
            continue
        try:
            d = json.loads(p.stdout)
        except json.JSONDecodeError as exc:   # one commit's patch carried an invalid \u escape
            (diffs / f"{c['sha']}.json").write_text(json.dumps({"error": f"unparseable api response: {exc}"}), encoding="utf-8")
            failed += 1
            continue
        keep = {"sha": c["sha"], "repo": c["repo"], "parents": [x["sha"] for x in d.get("parents", [])],
                "stats": d.get("stats"), "files": [{"filename": f["filename"], "status": f["status"], "additions": f["additions"],
                                                     "deletions": f["deletions"], "patch": f.get("patch") if TEST_PATH.search(f["filename"]) else None}
                                                    for f in d.get("files", [])]}
        (diffs / f"{c['sha']}.json").write_text(json.dumps(keep), encoding="utf-8")
        if i % 200 == 0:
            print(f"  {i}/{len(todo)} fetched, {failed} failed", flush=True)
        time.sleep(0.4)   # ~4,500/hour, under the budget with room for other work
    print(f"done: {len(todo) - failed} fetched, {failed} failed")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
