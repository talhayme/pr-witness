#!/usr/bin/env python3
"""PreToolUse: a pause before a test file changes.

Not a wall. The agent runs inside its own environment and can route around
any hook; the proof lives in CI. This is a polite question at the moment it
is most useful — "you are changing a test; is the behaviour meant to
change, or is the test in the way?" — asked once, with the reasoning, and
then the human decides.

Set PR_WITNESS_GUARD=deny for a hard no, or PR_WITNESS_GUARD=off to
silence it. Default is ask. Standard library only: this runs on every edit.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import sys

TEST_GLOBS = [
    "tests/**", "test/**", "**/tests/**", "**/test/**", "**/__tests__/**",
    "**/test_*.py", "**/*_test.py", "**/conftest.py",
    "**/*.test.ts", "**/*.test.tsx", "**/*.test.js", "**/*.test.jsx",
    "**/*.spec.ts", "**/*.spec.js", "**/*_test.go",
    "pytest.ini", "**/pytest.ini", "setup.cfg", "tox.ini",
    "**/vitest.config.*", "**/jest.config.*",
    ".github/workflows/**",
]

# Commands that remove, move or rewrite files, when aimed at a test path.
DESTRUCTIVE = re.compile(r"\b(rm|mv|sed|git\s+rm|git\s+mv|truncate|>)\b")


def is_test_path(path: str) -> bool:
    path = path.replace("\\", "/")
    # Only a leading "./" — lstrip("./") would also eat the dot of .github/.
    if path.startswith("./"):
        path = path[2:]
    for pattern in TEST_GLOBS:
        if fnmatch.fnmatch(path, pattern):
            return True
        if pattern.startswith("**/") and fnmatch.fnmatch(path, pattern[3:]):
            return True
        if pattern.endswith("/**") and path.startswith(pattern[:-2]):
            return True
    return False


def test_paths_in_command(command: str) -> list[str]:
    tokens = re.findall(r"[\w./\\-]+", command)
    return sorted({t for t in tokens if "/" in t or "." in t} & {t for t in tokens if is_test_path(t)})


def main() -> int:
    mode = os.environ.get("PR_WITNESS_GUARD", "ask").lower()
    if mode == "off":
        return 0

    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input", {}) or {}
    touched: list[str] = []
    verb = "edit"

    if tool in ("Edit", "Write", "MultiEdit"):
        path = tool_input.get("file_path", "")
        if path and is_test_path(path):
            touched = [path]
            verb = "write" if tool == "Write" else "edit"
    elif tool == "Bash":
        command = tool_input.get("command", "")
        if DESTRUCTIVE.search(command):
            touched = test_paths_in_command(command)
            verb = "remove or rewrite"

    if not touched:
        return 0

    shown = ", ".join(touched[:3]) + (" …" if len(touched) > 3 else "")
    reason = (
        f"pr-witness: this will {verb} a test file ({shown}).\n"
        "If the behaviour is meant to change, say so in the commit and update the "
        "test to describe the new behaviour. If the test is simply in the way, fix "
        "the code instead — CI will run the old test against the new code either way."
    )
    decision = "deny" if mode == "deny" else "ask"
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
