#!/usr/bin/env bash
# Run a batch of real cases one after another in the sandbox.
#
#   eval/run_batch.sh <source> <log> <case>...
#
# One case at a time, each under the sandbox's memory cap. A case that
# takes longer than CASE_LIMIT seconds has its container killed and is
# recorded as such — a stuck install must not hold the batch, or the laptop.
# After each case the evidence is kept and the clone, venv and node_modules
# are deleted, so disk use stays bounded by one case.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE="$1"; LOG="$2"; shift 2
CASE_LIMIT="${CASE_LIMIT:-1500}"
CACHE="${PR_WITNESS_SANDBOX_CACHE:-$HOME/.cache/pr-witness-real-sandbox}"
KEEP="$HOME/.cache/pr-witness-real/$SOURCE/evidence"
mkdir -p "$KEEP" "$(dirname "$LOG")"
cd "$ROOT"
for c in "$@"; do
  py=$(sed -n 's/^python: *//p' "corpus/real/$SOURCE/cases/$c/label.yaml" | head -1); py="${py:-3.12}"
  echo "### $(date +%H:%M:%S) start $c (python $py)" >> "$LOG"
  ./venv/bin/python eval/run_real.py --sandbox --source "$SOURCE" "$c" --python "$py" > "$LOG.$c" 2>&1 &
  pid=$!; t=0
  while kill -0 "$pid" 2>/dev/null; do
    sleep 10; t=$((t + 10))
    if [ "$t" -ge "$CASE_LIMIT" ]; then
      echo "### $(date +%H:%M:%S) LIMIT ${CASE_LIMIT}s reached for $c — killing its container" >> "$LOG"
      docker ps -q | xargs -r docker kill >/dev/null 2>&1
      sleep 5; kill "$pid" 2>/dev/null
    fi
  done
  grep -vE '^\s*·' "$LOG.$c" | cut -c1-400 >> "$LOG"; rm -f "$LOG.$c"
  [ -f "$CACHE/work/$c/evidence.json" ] && cp "$CACHE/work/$c/evidence.json" "$KEEP/$c.json"
  rm -rf "$CACHE/work/$c" "$CACHE/work/$c.base-probe"
  echo "### $(date +%H:%M:%S) done $c (${t}s)" >> "$LOG"
done
echo "### batch finished $(date +%H:%M:%S)" >> "$LOG"
