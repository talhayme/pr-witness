#!/usr/bin/env python3
"""report.json per instance — the harness's own verdict (resolved or not).
Needed because one submission's per_instance_details.json says False for
every instance while its metadata claims 69.6% resolved."""
import sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).parent
BUCKET = "https://swe-bench-submissions.s3.amazonaws.com/bash-only"
ids = [l.strip() for l in (HERE / "instances.txt").read_text().splitlines() if l.strip()]

def fetch(sub, iid):
    out = HERE / "reports" / sub / f"{iid}.json"
    if out.exists():
        return "cached"
    try:
        with urllib.request.urlopen(f"{BUCKET}/{sub}/logs/{iid}/report.json", timeout=60) as r:
            out.write_bytes(r.read()); return "ok"
    except Exception as e:  # noqa: BLE001
        return f"miss:{getattr(e, 'code', e)}"

for sub in sys.argv[1:]:
    (HERE / "reports" / sub).mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda i: fetch(sub, i), ids))
    print(f"{sub:46} ok {res.count('ok'):3}  cached {res.count('cached'):3}  missing {sum(r.startswith('miss') for r in res):3}", flush=True)
