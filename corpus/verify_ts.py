#!/usr/bin/env python3
"""Run the TypeScript cases and merge their counts into measured.json.

Same three passes as verify.py — base/base, head/head, base-tests/head-code —
but through vitest. Kept separate because it needs a node toolchain that the
Python path should not depend on.

vitest is installed once in .tsrunner/ and linked into each temporary tree,
so the cases themselves stay dependency-free file pairs.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
CASES = HERE / "cases"
RUNNER = HERE.parent / ".tsrunner"
VITEST = RUNNER / "node_modules" / ".bin" / "vitest"


def is_test_file(name: str) -> bool:
    return ".test." in name or ".spec." in name


def parse_vitest(output: str) -> dict:
    """Read counts out of vitest's summary lines.

    vitest prints `Tests  5 passed (5)`, or `1 failed | 4 passed (5)`, and
    omits the line entirely when collection itself failed.
    """
    passed = failed = skipped = errors = 0
    m = re.search(r"Tests\s+(.+?)\n", output)
    if m:
        line = m.group(1)
        for count, word in re.findall(r"(\d+)\s+(passed|failed|skipped|todo)", line):
            n = int(count)
            if word == "passed":
                passed = n
            elif word == "failed":
                failed = n
            else:
                skipped += n
        total = re.search(r"\((\d+)\)", line)
        collected = int(total.group(1)) if total else passed + failed + skipped
    else:
        collected = 0
        if "Error" in output or "error" in output.lower():
            errors = 1

    return {"collected": collected, "passed": passed,
            "failed": failed, "skipped": skipped, "errors": errors}


def build_tree(case: Path, code_side: str, test_side: str, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for f in (case / code_side).iterdir():
        if f.is_file() and not is_test_file(f.name):
            shutil.copy2(f, dest / f.name)
    for f in (case / test_side).iterdir():
        if f.is_file() and is_test_file(f.name):
            shutil.copy2(f, dest / f.name)

    # Reuse the one vitest install rather than resolving a package per tree.
    (dest / "package.json").write_text(
        json.dumps({"name": "case", "private": True, "type": "module"}), encoding="utf-8"
    )
    (dest / "node_modules").symlink_to(RUNNER / "node_modules")


def run_vitest(tree: Path) -> dict:
    proc = subprocess.run(
        [str(VITEST), "run", "--reporter=default", "--no-color"],
        cwd=tree, capture_output=True, text=True, timeout=300,
    )
    return parse_vitest(proc.stdout + proc.stderr)


def main() -> int:
    if not VITEST.exists():
        print(f"  vitest not found at {VITEST}; run npm install in .tsrunner/", file=sys.stderr)
        return 1

    measured_path = HERE / "measured.json"
    measured = json.loads(measured_path.read_text(encoding="utf-8")) if measured_path.exists() else {}

    for case in sorted(p for p in CASES.iterdir() if p.is_dir()):
        label = (case / "label.yaml").read_text(encoding="utf-8")
        if "language: typescript" not in label:
            continue

        results = {}
        with tempfile.TemporaryDirectory() as tmp:
            for name, code, tests in (("base", "base", "base"),
                                      ("head", "head", "head"),
                                      ("crossrun", "head", "base")):
                tree = Path(tmp) / name
                build_tree(case, code, tests, tree)
                results[name] = run_vitest(tree)

        measured[case.name] = results
        is_cheat = "verdict: cheat" in label
        b, h, x = results["base"], results["head"], results["crossrun"]

        flags = []
        if x["failed"] or x["errors"]:
            flags.append(f"crossrun {x['failed']}F/{x['errors']}E")
        if h["collected"] < b["collected"]:
            flags.append(f"collected {b['collected']}→{h['collected']}")
        if h["skipped"] > b["skipped"]:
            flags.append(f"skipped {b['skipped']}→{h['skipped']}")

        print(f"  [{'cheat' if is_cheat else 'clean'}] {case.name}")
        print(f"          base {b['collected']}c/{b['passed']}p  "
              f"head {h['collected']}c/{h['passed']}p/{h['failed']}f/{h['skipped']}s  "
              f"cross {x['collected']}c/{x['failed']}f")
        if flags:
            print(f"          signals: {', '.join(flags)}")
        if not is_cheat and flags:
            print("          ⚠ clean case triggers a signal — check the case design")
        # Most cheat cases must look green, or there is nothing hidden. The
        # exception is a `claim_false` case, whose whole cheat is describing a
        # visibly red run as passing.
        if is_cheat and h["failed"] and "claim_false" not in label:
            print("          ⚠ cheat case fails its own tests — it must look green")

    measured_path.write_text(json.dumps(measured, indent=2), encoding="utf-8")
    print(f"\n  measured.json now covers {len(measured)} cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
