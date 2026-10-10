#!/usr/bin/env bash
# Run a command inside a container that cannot take the host down.
#
#   eval/sandbox/safe-run.sh [-m 2g] [-c 1.5] [-v host:container ...] IMAGE CMD...
#
# Why this exists: a 5 GB parquet file froze a 16 GB laptop twice while
# being processed "carefully" — pyarrow kept whole row groups resident, and
# DuckDB's memory_limit does not cover its parquet read buffers. Limits set
# inside a program are promises; a cgroup limit is enforced by the kernel.
# If the command exceeds the cap it is killed (exit 137) and nothing else
# happens. Defaults: 2 GB, no swap, 1.5 CPUs, no network, no capabilities.
#
# On Docker Desktop (macOS/Windows) also cap the VM itself — Settings →
# Resources → Memory (e.g. 3 GB) — because that is the ceiling the host sees.
# Split big jobs into chunks, one child process per chunk, so a kill loses a
# chunk rather than the run (see corpus/real/swechat/extract_light.py).
set -euo pipefail
MEM=2g; CPUS=1.5; NET=none; VOLS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -m) MEM="$2"; shift 2;;
    -c) CPUS="$2"; shift 2;;
    -v) VOLS+=(-v "$2"); shift 2;;
    --net) NET="$2"; shift 2;;
    --) shift; break;;
    -*) echo "unknown flag $1" >&2; exit 2;;
    *) break;;
  esac
done
[[ $# -ge 2 ]] || { echo "usage: $0 [-m MEM] [-c CPUS] [-v host:ctr]... [--net none|bridge] IMAGE CMD..." >&2; exit 2; }
IMAGE="$1"; shift
exec docker run --rm --memory "$MEM" --memory-swap "$MEM" --cpus "$CPUS" --network "$NET" \
  --cap-drop ALL --security-opt no-new-privileges --pids-limit 512 \
  "${VOLS[@]}" "$IMAGE" "$@"
