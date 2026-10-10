#!/usr/bin/env python3
"""Materialise and run the reference cases in corpus/real/.

For each case: partial-clone the repository (cached), check out the base
commit, commit the agent's patch on top, build a virtualenv on a Python
the repository's era can run, install it, and run pr-witness restricted to
the test files the change touches. The result is compared with the label.

    python eval/run_real.py [case-id …] [--python 3.10]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "corpus" / "real" / "swebench" / "cases"
CACHE = Path(os.environ.get("PR_WITNESS_REAL_CACHE", Path.home() / ".cache" / "pr-witness-real"))
UV = shutil.which("uv") or str(Path.home() / ".local" / "bin" / "uv")


def sh(*args, cwd=None, check=True, timeout=1800, env=None):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
    if check and p.returncode:
        raise RuntimeError(f"{' '.join(map(str, args))}\n{p.stderr[-800:]}")
    return p


def label(case: Path) -> dict:
    d = {}
    for line in (case / "label.yaml").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^(\w+):\s*(.*)$", line)
        if m and m.group(2) and not m.group(2).startswith(">"):
            d[m.group(1)] = m.group(2).split("#")[0].strip()
    return d


def materialise(case: Path, lab: dict) -> Path:
    repo = lab["repo"]; base = lab["base_commit"]
    src = CACHE / "src" / repo.replace("/", "__")
    if not (src / ".git").exists():
        src.parent.mkdir(parents=True, exist_ok=True)
        sh("git", "clone", "--quiet", "--filter=blob:none", f"https://github.com/{repo}.git", str(src), timeout=3600)
    work = CACHE / "work" / case.name
    if work.exists():
        shutil.rmtree(work)
    sh("git", "-C", str(src), "fetch", "--quiet", "origin", base, check=False, timeout=3600)
    sh("git", "worktree", "prune", cwd=src)
    sh("git", "worktree", "add", "--quiet", "--detach", str(work), base, cwd=src, timeout=3600)
    sh("git", "apply", "--index", str(case / "agent.diff"), cwd=work)
    sh("git", "-c", "user.email=e@x", "-c", "user.name=agent", "commit", "-qm", f"agent patch for {case.name}", cwd=work)
    return work


def venv_for(work: Path, lab: dict, python: str) -> Path:
    venv = work / ".venv"
    sh(UV, "venv", "-q", "--python", python, str(venv))
    pip = [UV, "pip", "install", "-q", "--python", str(venv / "bin" / "python")]
    extras = {"sympy/sympy": ["mpmath"], "sphinx-doc/sphinx": [], "django/django": [], "matplotlib/matplotlib": []}.get(lab["repo"], [])
    sh(*pip, "pytest", "checkwash", "-e", ".", *extras, cwd=work, timeout=3600)
    # the pr-witness under test, from this checkout
    sh(*pip, "-e", str(ROOT), cwd=work, timeout=1800)
    return venv


def run_case(case: Path, python: str) -> dict:
    lab = label(case)
    work = materialise(case, lab)
    venv = venv_for(work, lab, python)
    ev_path = work / "evidence.json"
    p = subprocess.run([str(venv / "bin" / "pr-witness"), "--base", "HEAD~1", "--head", "HEAD", "--runner", "pytest",
                        "--changed-only", "--format", "json", "--evidence", str(ev_path), "--timeout", "1500"],
                       cwd=work, capture_output=True, text=True, timeout=3600)
    if not ev_path.exists():
        return {"case": case.name, "label": lab.get("verdict"), "error": (p.stderr or p.stdout)[-600:]}
    ev = json.loads(ev_path.read_text())
    return {"case": case.name, "label": lab.get("verdict"), "repo": lab["repo"], "verdict": ev["verdict"],
            "counts": ev["counts"], "findings": [(f["signal"], f["severity"], f["summary"]) for f in ev["findings"]],
            "notes": ev.get("notes", [])}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cases", nargs="*")
    ap.add_argument("--python", default="3.10")
    args = ap.parse_args()
    names = args.cases or sorted(p.name for p in CASES.iterdir() if p.is_dir())
    out = []
    for n in names:
        print(f"== {n}", flush=True)
        try:
            r = run_case(CASES / n, args.python)
        except Exception as exc:  # noqa: BLE001
            r = {"case": n, "error": str(exc)[-600:]}
        out.append(r)
        if "error" in r:
            print("   ERROR:", r["error"].strip().splitlines()[-1][:200], flush=True)
        else:
            c = r["counts"]
            print(f"   label={r['label']:7} tool={r['verdict']:6}  base {c['base']['passed']}/{c['base']['collected']}  head {c['head']['passed']}/{c['head']['collected']}  cross {c['crossrun']['failed']}F/{c['crossrun']['collected']}", flush=True)
            for sig, sev, summ in r["findings"]:
                print(f"      [{sev}] {sig}: {summ[:100]}", flush=True)
    (ROOT / "eval" / "real_results.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
