#!/usr/bin/env python3
"""Step 4: a shortlist for a human to read, with the code side attached.

Takes the ranked candidates and picks a handful per signal class — tests
deleted, assertions removed from existing tests, skips added to existing
tests, expected values changed in small commits — then fetches the *whole*
commit (code and tests) for those few and adds one cheap check: do the
symbols whose tests vanished still exist in the code after the commit? A
test removed with its function is cleanup; a test removed while the function
stays is the thing worth a label.

    python shortlist.py <dir> [--per-class 8]   → <dir>/shortlist.json + a readable dump
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

SYMBOL = re.compile(r"\b(?:describe|it|test)\(\s*['\"]([^'\"]+)|def (test_\w+)|\b([A-Za-z_]\w+)\(")


def gh_commit(repo: str, sha: str) -> dict | None:
    p = subprocess.run(["gh", "api", f"repos/{repo}/commits/{sha}"], capture_output=True, text=True)
    if p.returncode:
        return None
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        return None


def removed_symbols(test_patch: str) -> set[str]:
    """Identifiers called in removed test lines (the code under test), minus test-framework names."""
    noise = {"expect", "it", "describe", "test", "beforeEach", "afterEach", "beforeAll", "afterAll", "assert",
             "toBe", "toEqual", "require", "import", "print", "len", "str", "int", "list", "dict", "set", "range",
             "isinstance", "pytest", "raises", "mock", "patch", "jest", "vi", "fn", "Promise", "Error", "JSON",
             "Date", "Math", "Object", "Array", "String", "Number", "console", "join", "split", "map", "filter"}
    out = set()
    for line in test_patch.splitlines():
        if not line.startswith("-") or line.startswith("---"):
            continue
        for m in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]{2,})\(", line):
            name = m.group(1)
            if name not in noise and not name.startswith(("to", "assert")):
                out.add(name)
    return out


def main(data: Path, per_class: int) -> int:
    cands = json.loads((data / "candidates.json").read_text(encoding="utf-8"))
    classes = {
        "tests_deleted": [c for c in cands if c["deleted_tests"]],
        "assertions_removed": [c for c in cands if c["assertions_removed"] > c["assertions_added"] and not c["deleted_tests"]],
        "skips_added": [c for c in cands if c["skips_added"] > 0 and c["tests_modified"]],
        "expected_changed_small": sorted([c for c in cands if c["expected_changed"] > 0 and c["test_lines_removed"] + c["test_lines_added"] <= 40
                                          and not c["deleted_tests"]], key=lambda c: -c["expected_changed"]),
    }
    picked, seen = [], set()
    for cls, items in classes.items():
        for c in items:
            if len([p for p in picked if p["class"] == cls]) >= per_class:
                break
            if c["sha"] in seen:
                continue
            seen.add(c["sha"])
            picked.append({"class": cls, **c})
    print(f"shortlist: {len(picked)} commits: " + ", ".join(f"{k} {len([p for p in picked if p['class'] == k])}" for k in classes), file=sys.stderr)

    full_dir = data / "full"; full_dir.mkdir(exist_ok=True)
    for c in picked:
        f = full_dir / f"{c['sha']}.json"
        if not f.exists():
            d = gh_commit(c["repo"], c["sha"])
            if d is None:
                continue
            f.write_text(json.dumps(d), encoding="utf-8")
        d = json.loads(f.read_text(encoding="utf-8"))
        test_patch = "\n".join(x.get("patch") or "" for x in d["files"] if x["filename"] in c["test_files"])
        code_patch_added = "\n".join(l for x in d["files"] if x["filename"] not in c["test_files"]
                                     for l in (x.get("patch") or "").splitlines() if l.startswith("+"))
        code_patch_removed = "\n".join(l for x in d["files"] if x["filename"] not in c["test_files"]
                                       for l in (x.get("patch") or "").splitlines() if l.startswith("-"))
        syms = removed_symbols(test_patch)
        c["symbols_in_removed_tests"] = sorted(syms)[:12]
        c["symbols_also_removed_from_code"] = sorted(s for s in syms if re.search(rf"\b{re.escape(s)}\b", code_patch_removed))
        c["symbols_not_touched_in_code"] = sorted(s for s in syms if not re.search(rf"\b{re.escape(s)}\b", code_patch_removed + code_patch_added))
        c["code_files_changed"] = [{"f": x["filename"], "+": x["additions"], "-": x["deletions"]} for x in d["files"] if x["filename"] not in c["test_files"]][:8]
        c["url"] = f"https://github.com/{c['repo']}/commit/{c['sha']}"
    (data / "shortlist.json").write_text(json.dumps(picked, indent=1), encoding="utf-8")

    lines = []
    for c in picked:
        lines.append(f"[{c['class']}] {c['repo']} {c['sha'][:8]} — {c['message'][:80]}")
        lines.append(f"    tests: mod {len(c['tests_modified'])} del {len(c['deleted_tests'])} | -A{c['assertions_removed']} +A{c['assertions_added']} skip{c['skips_added']:+} exp{c['expected_changed']} | code files {len(c['code_files_changed'])}")
        if c.get("symbols_in_removed_tests"):
            lines.append(f"    symbols in removed tests: {', '.join(c['symbols_in_removed_tests'][:8])}")
            lines.append(f"      also removed from code: {', '.join(c['symbols_also_removed_from_code'][:8]) or '—'}")
            lines.append(f"      NOT touched in code:    {', '.join(c['symbols_not_touched_in_code'][:8]) or '—'}")
        lines.append(f"    {c['url']}")
    (data / "shortlist.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    per = int(sys.argv[sys.argv.index("--per-class") + 1]) if "--per-class" in sys.argv else 8
    sys.exit(main(Path(sys.argv[1]), per))
