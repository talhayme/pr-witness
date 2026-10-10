#!/usr/bin/env python3
"""Materialise and run the reference cases in corpus/real/.

For each case: partial-clone the repository (cached), check out the base
commit, commit the agent's patch on top, build a virtualenv on a Python
the repository's era can run, install it, and run pr-witness restricted to
the test files the change touches. The result is compared with the label.

    python eval/run_real.py [case-id …] [--python 3.10]
    python eval/run_real.py --sandbox [case-id …]     # inside Docker, see below

The project under test and the agent's patch are untrusted code. `--sandbox`
runs every stage in the `pr-witness-sandbox` image (eval/sandbox/Dockerfile):
clone + install with the network on, the test runs with it off, no host
directory mounted but a cache of this tool's own, no capabilities, a memory
and process ceiling. The host runs nothing but docker.
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
REAL = ROOT / "corpus" / "real"
CASES = REAL / "swebench" / "cases"   # default source; --source picks another
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
    head = lab.get("head_commit")
    if head:
        # A real commit (SWE-chat): check it out as is; its first parent is
        # the base, so --base HEAD~1 --head HEAD reads the commit itself.
        sh("git", "-C", str(src), "fetch", "--quiet", "origin", head, check=False, timeout=3600)
        sh("git", "worktree", "add", "--quiet", "--detach", str(work), head, cwd=src, timeout=3600)
        parent = sh("git", "rev-parse", "HEAD~1", cwd=work).stdout.strip()
        assert parent.startswith(base), f"{case.name}: first parent {parent[:10]} is not base_commit {base[:10]}"
        # The clone is blob-less; the run stage has no network. Touch every
        # object the base tree needs now, while we still can: a throwaway
        # worktree of the parent pulls the base versions of the changed files.
        sh("git", "diff", "--stat", "HEAD~1", "HEAD", cwd=work)
        probe = work.parent / (work.name + ".base-probe")
        sh("git", "worktree", "add", "--quiet", "--detach", str(probe), "HEAD~1", cwd=work, timeout=3600)
        sh("git", "worktree", "remove", "--force", str(probe), cwd=work)
        return work
    sh("git", "worktree", "add", "--quiet", "--detach", str(work), base, cwd=src, timeout=3600)
    sh("git", "apply", "--index", str(case / "agent.diff"), cwd=work)
    sh("git", "-c", "user.email=e@x", "-c", "user.name=agent", "commit", "-qm", f"agent patch for {case.name}", cwd=work)
    return work


def venv_for(work: Path, lab: dict, python: str) -> Path:
    venv = work / ".venv"
    if lab.get("install_cmd"):
        # A JavaScript (or otherwise non-Python) project: the label says how
        # to install; the runner comes from the label too. No venv.
        sh("sh", "-c", lab["install_cmd"], cwd=work, timeout=3600)
        return venv
    sh(UV, "venv", "-q", "--python", python, str(venv))
    pip = [UV, "pip", "install", "-q", "--python", str(venv / "bin" / "python")]
    # Only the project and its runner go into the case's venv. pr-witness
    # itself (and checkwash) run from this checkout's own environment and
    # reach the case's pytest through PATH — the repository's era may need
    # a Python that our dependencies no longer support.
    extras = {"sympy/sympy": ["mpmath"], "sphinx-doc/sphinx": [], "django/django": ["unittest-xml-reporting"], "matplotlib/matplotlib": []}.get(lab["repo"], [])
    extras += lab.get("install_extras", "").split()
    target = lab.get("install_target", "-e .")          # e.g. "-e .[dev]", "-r requirements.txt", "uv-lock"
    if target == "uv-lock":
        # The project's own resolution, including undeclared-but-locked
        # dependencies; every group and extra, since tests import freely.
        sh(UV, "export", "--frozen", "--no-hashes", "--all-extras", "--all-groups", "-o", str(work / ".pw-requirements.txt"), cwd=work, timeout=1800)
        sh(*pip, "pytest", "-r", str(work / ".pw-requirements.txt"), "-e", ".", *extras, cwd=work, timeout=7200)
        return venv
    sh(*pip, "pytest", *target.split(), *extras, cwd=work, timeout=3600)
    return venv


RUNNER = {"django/django": "django"}


def run_case(case: Path, python: str, stage: str = "all") -> dict:
    lab = label(case)
    work = CACHE / "work" / case.name
    if stage in ("all", "install"):
        work = materialise(case, lab)
        venv_for(work, lab, python)
        if stage == "install":
            return {"case": case.name, "stage": "installed"}
    venv = work / ".venv"
    ev_path = work / "evidence.json"
    env = {**os.environ, "PATH": f"{venv / 'bin'}{os.pathsep}{os.environ['PATH']}", "VIRTUAL_ENV": str(venv)}
    env.pop("PYTHONPATH", None)
    runner = lab.get("runner") or RUNNER.get(lab["repo"], "pytest")
    extra = lab.get("witness_args", "").split()
    # A label that names --paths chooses the files itself (a commit that
    # touches tests for two runners, say); otherwise every touched test file.
    scope = [] if "--paths" in extra else ["--changed-only"]
    witness_bin = ROOT / "venv" / "bin" / "pr-witness"
    if not witness_bin.exists():
        witness_bin = Path(shutil.which("pr-witness") or "pr-witness")
    p = subprocess.run([str(witness_bin), "--base", "HEAD~1", "--head", "HEAD", "--runner", runner,
                        *scope, *extra, "--format", "json", "--evidence", str(ev_path), "--timeout", "1500"],
                       cwd=work, capture_output=True, text=True, timeout=3600, env=env)
    if not ev_path.exists():
        return {"case": case.name, "label": lab.get("verdict"), "error": (p.stderr or p.stdout)[-600:]}
    ev = json.loads(ev_path.read_text())
    return {"case": case.name, "label": lab.get("verdict"), "repo": lab["repo"], "verdict": ev["verdict"],
            "counts": ev["counts"], "findings": [(f["signal"], f["severity"], f["summary"]) for f in ev["findings"]],
            "notes": ev.get("notes", [])}


SANDBOX_IMAGE = "pr-witness-sandbox"
SANDBOX_CACHE = Path(os.environ.get("PR_WITNESS_SANDBOX_CACHE", Path.home() / ".cache" / "pr-witness-real-sandbox"))


def run_sandboxed(case: Path, python: str) -> dict:
    """Two container runs: install (network on), run (network off)."""
    SANDBOX_CACHE.mkdir(parents=True, exist_ok=True)
    common = ["docker", "run", "--rm", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
              "--memory", "2500m", "--memory-swap", "2500m", "--pids-limit", "1024",
              "-v", f"{SANDBOX_CACHE}:/work/.cache", "-v", f"{ROOT / 'corpus'}:/opt/pr-witness/corpus:ro",
              SANDBOX_IMAGE, case.name, "--python", python, "--source", case.parent.parent.name]
    sh(*common[:3], "--network", "bridge", *common[3:], "--stage", "install", timeout=7200)
    sh(*common[:3], "--network", "none", *common[3:], "--stage", "run", timeout=7200)
    result = SANDBOX_CACHE / "work" / case.name / "result.json"
    return json.loads(result.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cases", nargs="*")
    ap.add_argument("--python", default="3.10")
    ap.add_argument("--stage", choices=["all", "install", "run"], default="all",
                    help="internal: one stage, used inside the sandbox container")
    ap.add_argument("--sandbox", action="store_true", help="run every stage inside Docker")
    ap.add_argument("--source", default="swebench", help="corpus/real/<source>/cases")
    args = ap.parse_args()
    global CASES
    CASES = REAL / args.source / "cases"
    names = args.cases or sorted(p.name for p in CASES.iterdir() if p.is_dir())
    out = []
    for n in names:
        print(f"== {n}", flush=True)
        try:
            if args.sandbox:
                r = run_sandboxed(CASES / n, args.python)
            else:
                r = run_case(CASES / n, args.python, args.stage)
                if args.stage == "run":
                    (CACHE / "work" / n / "result.json").write_text(json.dumps(r), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            r = {"case": n, "error": str(exc)[-600:]}
        if r.get("stage") == "installed":
            print("   installed", flush=True)
            continue
        out.append(r)
        if "error" in r:
            print("   ERROR:", r["error"].strip().splitlines()[-1][:200], flush=True)
        else:
            c = r["counts"]
            mark = "✓" if {"note": "clean"}.get(r["verdict"], r["verdict"]) == r["label"] else "✗"
            print(f"   {mark} label={r['label']:7} tool={r['verdict']:6}  base {c['base']['passed']}/{c['base']['collected']}  head {c['head']['passed']}/{c['head']['collected']}  cross {c['crossrun']['failed']}F/{c['crossrun']['collected']}", flush=True)
            for sig, sev, summ in r["findings"]:
                print(f"      [{sev}] {sig}: {summ[:300]}", flush=True)
            for n in r["notes"]:
                print(f"      · {n[:300]}", flush=True)
    # Merge with earlier runs so the file holds every case run so far, not
    # only this invocation's.
    if args.stage != "all":
        return 0
    results_path = ROOT / "eval" / ("real_results.json" if args.source == "swebench" else f"real_results_{args.source}.json")
    previous = json.loads(results_path.read_text(encoding="utf-8")) if results_path.exists() else []
    merged = {r["case"]: r for r in previous}
    merged.update({r["case"]: r for r in out})
    results_path.write_text(json.dumps([merged[k] for k in sorted(merged)], indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
