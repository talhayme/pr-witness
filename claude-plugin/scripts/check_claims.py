#!/usr/bin/env python3
"""Stop: when the last message says the tests pass, find out whether they do.

Fires only when the message makes a checkable claim — "all tests pass",
"12/12 green", "added tests for X" — and then runs pr-witness on the working
tree against the base branch, feeding it that very message as the "pull
request description". Any claim the run contradicts is shown in the session.

Advisory by design: it adds context, it never blocks the stop. A hook that
refused to let the agent finish until the numbers matched would teach the
agent to stop making numbers, which is the opposite of the point.

Needs pr-witness on PATH. Without it, says so once and steps aside.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

# A cheap pre-filter so an ordinary message does not trigger three test
# runs. The real extraction happens inside pr-witness.
CLAIM_HINT = re.compile(
    r"\b\d+\s*(?:/\s*\d+\s*)?(?:tests?\s+)?(?:pass|passed|passing|green)\b"
    r"|\ball\s+(?:\d+\s+)?tests?\s+(?:still\s+)?(?:pass|passing|green)\b"
    r"|\bsuite\s+(?:is\s+)?(?:green|passing)\b|\btests?\s+(?:are\s+)?green\b"
    r"|\badded\s+(?:\d+\s+)?(?:new\s+)?tests?\b|\bno\s+breaking\s+changes?\b"
    r"|все\s+тесты\s+проход|тест\w*\s+прош|добав\w+\s+\d+\s+тест",
    re.I,
)


def context(text: str) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": text}}))


def base_ref(cwd: str) -> str | None:
    forced = os.environ.get("PR_WITNESS_BASE")
    if forced:
        return forced
    for candidate in ("origin/main", "origin/master", "main", "master"):
        ok = subprocess.run(["git", "rev-parse", "--verify", "-q", candidate],
                            cwd=cwd, capture_output=True)
        if ok.returncode == 0:
            return candidate
    return None


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    message = event.get("last_assistant_message", "") or ""
    if not CLAIM_HINT.search(message):
        return 0

    cwd = event.get("cwd") or os.getcwd()
    if not shutil.which("pr-witness"):
        context("pr-witness: this message claims a test result, but pr-witness is not "
                "installed so it was not checked (pip install pr-witness).")
        return 0

    base = base_ref(cwd)
    if base is None:
        context("pr-witness: could not find a base branch (origin/main or main); set PR_WITNESS_BASE.")
        return 0

    # Uncommitted work is what the agent is talking about, so witness the
    # working tree: commit it to a throwaway ref rather than ask the agent
    # to commit first.
    with tempfile.TemporaryDirectory() as tmp:
        body = os.path.join(tmp, "message.md")
        with open(body, "w", encoding="utf-8") as fh:
            fh.write(message)
        evidence = os.path.join(tmp, "evidence.json")

        head = "HEAD"
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=cwd,
                               capture_output=True, text=True).stdout.strip()
        if dirty:
            stash = subprocess.run(["git", "stash", "create"], cwd=cwd,
                                   capture_output=True, text=True).stdout.strip()
            if stash:
                head = stash

        proc = subprocess.run(
            ["pr-witness", "--base", base, "--head", head, "--pr-body", body,
             "--format", "json", "--evidence", evidence, "--timeout", "240"],
            cwd=cwd, capture_output=True, text=True, timeout=540,
        )
        try:
            with open(evidence, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            tail = (proc.stderr or proc.stdout).strip().splitlines()[-2:]
            context("pr-witness could not run: " + " ".join(tail))
            return 0

    bad = [c for c in data.get("claims", []) if c["verdict"] in ("false", "misleading")]
    high = [f for f in data.get("findings", []) if f["severity"] == "high"]
    if not bad and not high:
        return 0

    lines = ["pr-witness checked this message against a real run:"]
    for c in bad:
        mark = "✗" if c["verdict"] == "false" else "!"
        lines.append(f'  {mark} "{c["quote"]}" — {c["because"]}')
    for f in high[:3]:
        lines.append(f"  !! {f['signal']}: {f['summary']}")
    lines.append("Say what actually happened, with the real numbers, before finishing.")
    context("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
