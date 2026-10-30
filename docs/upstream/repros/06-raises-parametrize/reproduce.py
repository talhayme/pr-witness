"""Run both test forms and checkwash versions in a disposable Git repository.

Use a Python with pytest installed. Output is written only to --output and a
TemporaryDirectory. No network, changes to checkwash, or upstream publication.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkwash", action="append", required=True,
                        help="Path to a checkwash executable; repeat for each version")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = {"python": sys.version, "pytest": [], "checkwash": []}

    with tempfile.TemporaryDirectory(prefix="raises-parametrize-") as tmp:
        repo = Path(tmp)

        def git(*parts):
            return subprocess.run(
                ["git", "-c", "user.name=Reproduction", "-c",
                 "user.email=repro@example.invalid", *parts], cwd=repo,
                text=True, capture_output=True, check=True,
            )

        git("init", "-q")
        good = (HERE / "app.py").read_text(encoding="utf-8")
        mutant = "def checked(x):\n    return x\n"
        (repo / "app.py").write_text(good, encoding="utf-8")
        for side in ("before", "after"):
            (repo / "test_app.py").write_text(
                (HERE / f"{side}.py").read_text(encoding="utf-8"), encoding="utf-8")
            git("add", "app.py", "test_app.py")
            git("commit", "-qm", side)

        for index, executable in enumerate(args.checkwash):
            run = subprocess.run(
                [str(Path(executable).resolve()), "check", "HEAD~1..HEAD", "--format", "json"],
                cwd=repo, text=True, encoding="utf-8", capture_output=True, timeout=60,
            )
            document = json.loads(run.stdout)
            version = document["run"]["checkwash_version"]
            filename = f"checkwash-{index}-{version}.json"
            (args.output / filename).write_text(run.stdout, encoding="utf-8")
            results["checkwash"].append({
                "version": version, "exit_code": run.returncode,
                "verdict": document["verdict"], "output": filename, "stderr": run.stderr,
            })

        for side in ("before", "after"):
            (repo / "test_app.py").write_text(
                (HERE / f"{side}.py").read_text(encoding="utf-8"), encoding="utf-8")
            for implementation, source in (("good", good), ("no_range_check", mutant)):
                (repo / "app.py").write_text(source, encoding="utf-8")
                run = subprocess.run(
                    [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "test_app.py"],
                    cwd=repo, text=True, encoding="utf-8", capture_output=True, timeout=60,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
                         "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
                )
                expected = 0 if implementation == "good" else 1
                if run.returncode != expected:
                    raise RuntimeError(f"{side}/{implementation}: {run.stdout}\n{run.stderr}")
                filename = f"pytest-{side}-{implementation}.txt"
                (args.output / filename).write_text(run.stdout + run.stderr, encoding="utf-8")
                results["pytest"].append({"side": side, "implementation": implementation,
                                          "exit_code": run.returncode, "output": filename})

    (args.output / "summary.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
