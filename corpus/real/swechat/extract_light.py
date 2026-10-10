#!/usr/bin/env python3
"""Step 1 of mining SWE-chat: shrink commits.parquet to what the filter needs.

The 5 GB table is heavy in two columns — `patch` (the diff) and
`file_attribution`, whose JSON carries the *full text* of every file's agent
and committed versions. Neither is needed to decide whether a commit is a
candidate. This writes `commits_light.parquet`: the cheap columns and, from
the attribution JSON, only the per-file label.

Memory is the whole design. One row group at a time, each in a child
process, so a group too big for the container's limit kills only that child
(exit 137) and is recorded as skipped rather than taking the run down. A
group whose attribution column alone exceeds ATTRIBUTION_CAP bytes is read
without it — those rows are the giant diffs, not the test edits we want.
Runs inside the sandbox container under a kernel memory limit.

    python extract_light.py commits.parquet commits_light.parquet
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ATTRIBUTION_CAP = 150 * 1024 * 1024
LIGHT = ["commit_sha", "repo_id", "status", "is_agent_author", "author_name", "commit_date",
         "commit_message", "files_changed", "total_additions", "total_deletions"]


def one_group(src: Path, g: int, out: Path) -> None:
    pf = pq.ParquetFile(src)
    rg = pf.metadata.row_group(g)
    names = pf.schema_arrow.names
    attr_size = rg.column(names.index("file_attribution")).total_uncompressed_size
    cols = LIGHT + (["file_attribution"] if attr_size <= ATTRIBUTION_CAP else [])
    t = pf.read_row_group(g, columns=cols)
    rows = []
    for row in t.to_pylist():
        labels = None
        raw = row.pop("file_attribution", None)
        if raw:
            try:
                parsed = json.loads(raw) if isinstance(raw, str) else raw
                labels = {f: (v.get("attribution") if isinstance(v, dict) else v) for f, v in parsed.items()}
            except (ValueError, AttributeError):
                labels = None
        row["commit_message"] = (row["commit_message"] or "")[:200]
        row["attribution_labels"] = json.dumps(labels) if labels is not None else None
        row["attribution_read"] = attr_size <= ATTRIBUTION_CAP
        rows.append(row)
    del t
    pq.write_table(pa.Table.from_pylist(rows), out)


def main(src: Path, out: Path) -> int:
    pf = pq.ParquetFile(src)
    n = pf.metadata.num_row_groups
    shards = out.parent / (out.stem + "_shards")
    shards.mkdir(exist_ok=True)
    skipped = []
    for g in range(n):
        shard = shards / f"{g:05d}.parquet"
        if shard.exists():
            continue
        p = subprocess.run([sys.executable, __file__, "--group", str(g), str(src), str(shard)])
        if p.returncode != 0:
            skipped.append(g)
            print(f"  group {g}: child exited {p.returncode} — skipped", flush=True)
        if g % 100 == 0:
            print(f"  {g}/{n} row groups", flush=True)
    tables = [pq.read_table(s) for s in sorted(shards.glob("*.parquet"))]
    merged = pa.concat_tables(tables, promote_options="default")
    pq.write_table(merged, out)
    print(f"{out}: {merged.num_rows} rows, {out.stat().st_size/1e6:.1f} MB; row groups skipped: {skipped or 'none'}")
    return 0


if __name__ == "__main__":
    if sys.argv[1] == "--group":
        one_group(Path(sys.argv[3]), int(sys.argv[2]), Path(sys.argv[4]))
    else:
        sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
