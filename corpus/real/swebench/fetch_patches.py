#!/usr/bin/env python3
"""Download each submission's final agent patch per instance from the public
SWE-bench submissions bucket. Resumable; small files; a few threads."""
import sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).parent
BUCKET = "https://swe-bench-submissions.s3.amazonaws.com/bash-only"
ids = [l.strip() for l in (HERE / "instances.txt").read_text().splitlines() if l.strip()]

def fetch(sub, iid):
    out = HERE / "patches" / sub / f"{iid}.diff"
    if out.exists():
        return "cached"
    try:
        with urllib.request.urlopen(f"{BUCKET}/{sub}/logs/{iid}/patch.diff", timeout=60) as r:
            out.write_bytes(r.read()); return "ok"
    except Exception as e:  # noqa: BLE001
        return f"miss:{getattr(e, 'code', e)}"

for sub in sys.argv[1:]:
    (HERE / "patches" / sub).mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda i: fetch(sub, i), ids))
    print(f"{sub:46} ok {res.count('ok'):3}  cached {res.count('cached'):3}  missing {sum(r.startswith('miss') for r in res):3}", flush=True)
