# Sandbox: running untrusted or heavy work without taking the machine down

Two separate reasons to run things here:

1. **Untrusted code.** A real pull request's tests are someone else's code.
   `eval/run_real.py --sandbox` runs each case in `pr-witness-sandbox`
   (Dockerfile here): install with the network on, tests with it off.
2. **Heavy data.** A 5 GB parquet froze a 16 GB laptop twice during this
   project, both times under a program-level memory limit that was not
   honoured (pyarrow holds whole row groups; DuckDB's `memory_limit`
   excludes its parquet read buffers). The fix is not a better estimate but
   a kernel-enforced cap: `safe-run.sh` wraps any command in a container
   with `--memory`, no swap, no network, no capabilities. Exceed it and the
   process is killed — nothing else happens.

Rules that came out of the two crashes:

- Cap the Docker Desktop VM itself (Settings → Resources → Memory, 3 GB on
  a 16 GB machine). The container cap is enforced inside the VM; the VM cap
  is what the host actually sees.
- One child process per chunk, so a kill loses a chunk, not the run
  (`corpus/real/swechat/extract_light.py`: one row group per child, a
  killed group is recorded as skipped).
- Shrink first, think later: drop the heavy columns into a small file once,
  under the cap, and do every later step on the small file.
- Watch while it runs: `docker stats --no-stream` next to the host's memory
  (`top -l 1 | grep PhysMem` on macOS) in a loop; stop on the first surprise.
- Keep console output small. A 600 KB tool result was part of the second
  crash.

```bash
eval/sandbox/safe-run.sh -m 2g -v "$PWD":/data pr-witness-duck \
    python /data/extract_light.py /data/commits.parquet /data/commits_light.parquet
```
