#!/usr/bin/env python3
"""Pick a batch of cases by a rule written down before any of them is run.

The first seven SWE-chat cases were chosen by eye and the tool was changed
after each. This selects the next batch mechanically, so that running it
with the tool frozen measures something:

  * ranked candidates (rank > 0), repositories already in the corpus excluded;
  * every changed test file is Python under tests/ or test/, or a
    *.test/*.spec JS/TS file outside apps/ and packages/ (monorepos);
  * at most 25 files in the commit and 300 changed test lines — small
    enough for a human to label by reading;
  * a class from the test-side diff: tests_deleted, skips_added,
    assertions_removed, expected_changed — at most QUOTA per class;
  * one commit per repository, in rank order;
  * the repository can plausibly be installed in the sandbox: a root
    pyproject/setup (no torch/tensorflow/jax/transformers), or a root
    package.json with vitest or `bun test`, a lock file, no workspaces.

Every candidate looked at is recorded with the reason it was taken or left.
Labels are written by hand afterwards, before the runs.

    python prepare_batch.py <cache dir> [--size 20] [--quota 5]
"""
from __future__ import annotations

import base64
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
USED = {"manderson240/cohezion", "gilad-rubin/hypergraph", "marcus-sa/brain",
        "oddessentials/ado-git-repo-insights", "dylan-112/OpenACP", "dsa110/dsa110-FLITS"}
HEAVY = re.compile(r"\b(torch|tensorflow|jax|transformers|sentence-transformers|pyspark)\b", re.I)


def gh(path: str):
    p = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if p.returncode:
        return None
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        return None


def content(repo: str, sha: str, path: str) -> str | None:
    d = gh(f"repos/{repo}/contents/{path}?ref={sha}")
    if not isinstance(d, dict) or "content" not in d:
        return None
    return base64.b64decode(d["content"]).decode("utf-8", "replace")


def language(c: dict) -> str | None:
    t = c["test_files"]
    if all(f.endswith(".py") for f in t):
        return "python" if all(f.startswith(("tests/", "test/")) for f in t) else None
    if all(re.search(r"\.(test|spec)\.[cm]?[jt]sx?$", f) for f in t):
        return None if any(f.startswith(("apps/", "packages/")) for f in t) else "typescript"
    return None


def klass(c: dict) -> str | None:
    if c["deleted_tests"]:
        return "tests_deleted"
    if c["skips_added"] > 0 and c["tests_modified"]:
        return "skips_added"
    if c["assertions_removed"] > c["assertions_added"]:
        return "assertions_removed"
    if c["expected_changed"] > 0:
        return "expected_changed"
    return None


def feasible(c: dict, lang: str) -> tuple[dict | None, str]:
    repo, sha = c["repo"], c["sha"]
    root = gh(f"repos/{repo}/contents?ref={sha}")
    if not isinstance(root, list):
        return None, "repository or commit not reachable"
    names = {x["name"] for x in root}
    if lang == "python":
        if not names & {"pyproject.toml", "setup.py", "setup.cfg"}:
            return None, "no root pyproject/setup"
        text = content(repo, sha, "pyproject.toml") or ""
        if HEAVY.search(text) or HEAVY.search(content(repo, sha, "requirements.txt") or ""):
            return None, "heavy ML dependency"
        py = "3.13" if re.search(r">=\s*3\.1[34]", text) else "3.11" if re.search(r"<\s*3\.12", text) else "3.12"
        extras = []
        if "--cov" in text or "pytest-cov" in text:
            extras.append("pytest-cov")
        if "asyncio_mode" in text or "pytest-asyncio" in text or "pytest_asyncio" in text:
            extras.append("pytest-asyncio")
        if re.search(r"addopts[^\n]*-n\s", text) or "pytest-xdist" in text:
            extras.append("pytest-xdist")
        if "pytest-timeout" in text or re.search(r"^\s*timeout\s*=", text, re.M):
            extras.append("pytest-timeout")
        if "pytest-mock" in text:
            extras.append("pytest-mock")
        target = "-e ."
        for extra in ("dev", "test", "tests", "testing"):
            if re.search(rf"^\s*{extra}\s*=\s*\[", text, re.M) and "[project.optional-dependencies]" in text:
                target = f"-e .[{extra}]"
                break
        if "uv.lock" in names and "[dependency-groups]" in text:
            target = "uv-lock"
        return {"python": py, "install_target": target, "install_extras": " ".join(extras)}, "ok"
    if "package.json" not in names:
        return None, "no root package.json"
    try:
        pkg = json.loads(content(repo, sha, "package.json") or "{}")
    except json.JSONDecodeError:
        return None, "unreadable package.json"
    if pkg.get("workspaces"):
        return None, "workspaces (monorepo)"
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    test_script = pkg.get("scripts", {}).get("test", "")
    if "bun test" in test_script:
        runner = "bun"
    elif "vitest" in deps:
        runner = "vitest"
    else:
        return None, "no vitest or bun test at the root"
    if names & {"bun.lock", "bun.lockb"}:
        install = "bun install --frozen-lockfile || bun install"
    elif "pnpm-lock.yaml" in names:
        install = "corepack pnpm install --frozen-lockfile"
    elif "package-lock.json" in names:
        install = "npm ci"
    else:
        return None, "no bun/pnpm/npm lock file"
    return {"runner": runner, "install_cmd": install}, "ok"


def main(data: Path, size: int, quota: int) -> int:
    cands = json.loads((data / "candidates.json").read_text(encoding="utf-8"))
    taken, log, per_class, repos = [], [], {}, set()
    for c in cands:
        if len(taken) >= size:
            break
        if c["rank"] <= 0 or c["repo"] in USED or c["repo"] in repos:
            continue
        lang, k = language(c), klass(c)
        if not lang or not k:
            continue
        if len(c["test_files"]) + len(c["code_files"]) > 25 or c["test_lines_removed"] + c["test_lines_added"] > 300:
            continue
        if per_class.get(k, 0) >= quota:
            continue
        how, why = feasible(c, lang)
        log.append({"repo": c["repo"], "sha": c["sha"][:8], "class": k, "rank": c["rank"], "decision": why})
        if how is None:
            continue
        repos.add(c["repo"]); per_class[k] = per_class.get(k, 0) + 1
        taken.append({**{f: c[f] for f in ("repo", "sha", "parent", "message", "license", "rank", "test_files")},
                      "class": k, "language": lang, **how})
    (HERE / "batch1_selection.json").write_text(json.dumps({"taken": taken, "considered": log}, indent=1), encoding="utf-8")

    full = data / "full"; full.mkdir(exist_ok=True)
    for t in taken:
        f = full / f"{t['sha']}.json"
        if not f.exists():
            d = gh(f"repos/{t['repo']}/commits/{t['sha']}")
            if d:
                f.write_text(json.dumps(d), encoding="utf-8")
        name = re.sub(r"[^a-z0-9]+", "-", t["repo"].split("/")[1].lower()).strip("-") + "-" + t["sha"][:8]
        case = HERE / "cases" / name
        case.mkdir(parents=True, exist_ok=True)
        lines = [f"id: swechat/{name}", "verdict: TBD", "legitimacy: TBD", f"language: {t['language']}", "batch: 1",
                 "source: SWE-chat (SALT-NLP/SWE-chat, ODC-BY), commit by a coding-agent session",
                 f"repo: {t['repo']}", f"base_commit: {t['parent']}", f"head_commit: {t['sha']}", f"class: {t['class']}",
                 "summary: TBD"]
        for key in ("python", "install_target", "install_extras", "runner", "install_cmd"):
            if t.get(key):
                lines.append(f"{key}: {t[key]}")
        lines += ["witness_args: --timeout 600",
                  f"license: {t['license']} repository; diff referenced by commit. Dataset ODC-BY. Referenced as owner/repo and commit only."]
        (case / "label.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
        t["case"] = name
    (HERE / "batch1_selection.json").write_text(json.dumps({"taken": taken, "considered": log}, indent=1), encoding="utf-8")
    print(f"considered {len(log)}, taken {len(taken)}: " + ", ".join(f"{k} {v}" for k, v in per_class.items()))
    for t in taken:
        print(f"  {t['case']:40} {t['class']:19} {t['language']:10} rank {t['rank']:3} | {t['message'][:60]}")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    size = int(args[args.index("--size") + 1]) if "--size" in args else 20
    quota = int(args[args.index("--quota") + 1]) if "--quota" in args else 5
    sys.exit(main(Path(args[0]), size, quota))
