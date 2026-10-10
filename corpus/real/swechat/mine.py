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

# commits.parquet is 5 GB and a single row group holds up to 400 MB of
# diffs. pyarrow kept whole row groups resident and took this laptop down
# once; DuckDB streams the file under a hard memory limit instead, and the
# patch column is read only for the commits that pass the cheap filter.
MEMORY_LIMIT = "3GB"

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
        elif current and line[:1] in ("+", "-") and not line.startswith(("+++", "---")):
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
    import duckdb
    import resource

    def rss_mb() -> float:
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)

    con = duckdb.connect()
    con.execute(f"SET memory_limit='{MEMORY_LIMIT}'; SET threads=1; SET preserve_insertion_order=false; SET temp_directory='{data}/.duckdb-tmp';")
    repos = con.execute("SELECT repo_id, url, license_type FROM read_parquet(?)", [str(data / "repositories.parquet")]).fetchall()
    open_source = {"mit", "mit-0", "apache-2.0", "bsd-2-clause", "bsd-3-clause", "isc", "gpl-3.0", "gpl-2.0",
                   "agpl-3.0", "agplv3", "lgpl-3.0", "lgpl-2.1", "mpl-2.0", "cc0 1.0 universal", "unlicense", "0bsd"}
    usable = {r[0]: {"url": r[1], "license_type": r[2]} for r in repos if (r[2] or "").lower() in open_source}
    print(f"repositories: {len(repos)}, with an open-source licence: {len(usable)}", file=sys.stderr)
    con.execute("CREATE TABLE usable AS SELECT * FROM (VALUES " + ",".join("(?)" for _ in usable) + ") t(repo_id)", list(usable))

    # Pass 1 in SQL: cheap columns only. The name-status list says whether a
    # test file and a non-test file are both touched; the patch is not read.
    test_re = TEST_PATH.pattern
    q = f"""
        SELECT commit_sha, repo_id, is_agent_author, files_changed, file_attribution, commit_message
        FROM read_parquet(?) c JOIN usable USING (repo_id)
        WHERE status = 'ok' AND commit_sha IS NOT NULL
          AND regexp_matches(files_changed, '(?m){test_re}')
    """
    rows = con.execute(q, [str(data / "commits.parquet")]).fetchall()
    print(f"pass 1: {len(rows)} commits touch a test file in a usable repository, rss {rss_mb():.0f} MB", file=sys.stderr)

    keep = {}
    for sha, repo, agent, files_changed, attribution, message in rows:
        names = [l.split("\t")[-1] for l in (files_changed or "").splitlines() if l.strip()]
        tests = [f for f in names if TEST_PATH.search(f)]
        code = [f for f in names if not TEST_PATH.search(f)]
        if not tests or not code or sha in keep:
            continue
        attr = json.loads(attribution or "{}") if isinstance(attribution, str) else (attribution or {})
        if not (agent or any(attr.get(f) in ("agent_only", "mixed") for f in tests)):
            continue
        keep[sha] = {"repo": repo, "message": (message or "").splitlines()[0][:120] if message else "", "attribution": attr, "agent_author": bool(agent)}
    print(f"        {len(keep)} of them agent-attributed with code + test files", file=sys.stderr)

    # Pass 2: the diff of those commits only, streamed one row at a time.
    con.execute("CREATE TABLE keep AS SELECT * FROM (VALUES " + ",".join("(?)" for _ in keep) + ") t(commit_sha)", list(keep))
    cur = con.execute("SELECT commit_sha, patch FROM read_parquet(?) c JOIN keep USING (commit_sha) WHERE status = 'ok'",
                      [str(data / "commits.parquet")])
    out, seen, n = [], set(), 0
    while (row := cur.fetchone()) is not None:
        sha, patch = row
        if sha in seen:
            continue
        seen.add(sha)
        n += 1
        files = split_patch(patch or "")
        tests = [f for f in files if TEST_PATH.search(f)]
        code = [f for f in files if not TEST_PATH.search(f)]
        if not tests or not code:
            continue
        m = keep[sha]
        s = score([l for f in tests for l in files[f]])
        s["rank"] = 3 * s["assertions_removed"] + 4 * max(s["skips_added"], 0) + max(s["test_lines_removed"] - s["test_lines_added"], 0) // 5
        out.append({"repo": m["repo"], "url": usable[m["repo"]]["url"], "license": usable[m["repo"]]["license_type"],
                    "sha": sha, "message": m["message"], "test_files": tests, "code_files": code[:10],
                    "attribution": {f: m["attribution"].get(f) for f in tests}, "agent_author": m["agent_author"], **s})
        if n % 500 == 0:
            print(f"  pass 2: {n}/{len(keep)}, rss {rss_mb():.0f} MB", file=sys.stderr)
    out.sort(key=lambda c: -c["rank"])
    (data / "candidates.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"{len(out)} candidates (agent-attributed, test + code files, open-source licence); peak rss {rss_mb():.0f} MB")
    print(f"  with assertions removed: {sum(c['assertions_removed'] > 0 for c in out)}")
    print(f"  with skips added:        {sum(c['skips_added'] > 0 for c in out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
