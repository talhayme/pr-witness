"""Git plumbing: find the base, and build the cross-run working tree.

The cross-run needs a tree holding the pull request's code and the base
branch's tests. Building it by checking files out over the working copy
would leave the user's repository modified if anything went wrong, so every
run happens in a throwaway worktree instead. The user's checkout is never
touched.
"""

from __future__ import annotations

import fnmatch
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

# Where tests live, per ecosystem. Overridable via .pr-witness.yml; these are
# the defaults from the plan.
DEFAULT_TEST_GLOBS = [
    "tests/**",
    "test/**",
    "**/test_*.py",
    "**/*_test.py",
    "**/*.test.ts",
    "**/*.test.tsx",
    "**/*.test.js",
    "**/*.spec.ts",
    "**/*.spec.js",
    "**/*_test.go",
    "conftest.py",
    "**/conftest.py",
    "pytest.ini",
    "vitest.config.ts",
    "jest.config.js",
]


class GitError(RuntimeError):
    pass


def git(*args: str, cwd: Path, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True,
    )
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args)}: {proc.stderr.strip()}")
    return proc.stdout.strip()


def repo_root(start: Path) -> Path:
    return Path(git("rev-parse", "--show-toplevel", cwd=start))


def resolve(rev: str, cwd: Path) -> str:
    return git("rev-parse", rev, cwd=cwd)


def merge_base(base: str, head: str, cwd: Path) -> str:
    """The commit the branch actually diverged from.

    Comparing against the tip of main would attribute every change made on
    main since the branch started to this pull request's author, which is
    both wrong and rude.
    """
    try:
        return git("merge-base", base, head, cwd=cwd)
    except GitError:
        return resolve(base, cwd=cwd)


def changed_files(base: str, head: str, cwd: Path) -> list[str]:
    out = git("diff", "--name-only", f"{base}..{head}", cwd=cwd)
    return [line for line in out.splitlines() if line]


def matches_glob(path: str, pattern: str) -> bool:
    """Match a repository path against one glob, the way git would.

    `fnmatch` alone is not enough: it does not know that `**/` means "at any
    depth, including none", nor that `tests/**` should match everything
    under `tests/`. Both are spellings the plan's default globs rely on.
    """
    if fnmatch.fnmatch(path, pattern):
        return True
    if pattern.startswith("**/") and fnmatch.fnmatch(path, pattern[3:]):
        return True
    if pattern.endswith("/**") and path.startswith(pattern[:-2]):
        return True
    return False


def test_files_at(rev: str, cwd: Path, globs: list[str] | None = None) -> list[str]:
    """Test files as they exist at a given revision."""
    patterns = globs or DEFAULT_TEST_GLOBS
    files = git("ls-tree", "-r", "--name-only", rev, cwd=cwd).splitlines()
    return sorted(
        f for f in files if any(matches_glob(f, p) for p in patterns)
    )


@contextmanager
def worktree(rev: str, cwd: Path) -> Iterator[Path]:
    """A detached worktree at `rev`, removed afterwards.

    A worktree rather than a clone: it shares the object store, so this is
    near-instant even on a large repository.
    """
    with tempfile.TemporaryDirectory(prefix="pr-witness-") as tmp:
        path = Path(tmp) / "tree"
        git("worktree", "add", "--detach", "--quiet", str(path), rev, cwd=cwd)
        try:
            yield path
        finally:
            # --force because the test run may have left artefacts behind.
            git("worktree", "remove", "--force", str(path), cwd=cwd, check=False)


@contextmanager
def crossrun_tree(base_rev: str, head_rev: str, cwd: Path,
                  globs: list[str] | None = None) -> Iterator[Path]:
    """Head's code with base's tests: the combination CI never runs.

    Built by checking out the head revision, then overlaying the base
    revision's test files — and deleting test files that head added, so the
    base suite is reproduced exactly rather than approximately.
    """
    with worktree(head_rev, cwd) as tree:
        head_tests = set(test_files_at(head_rev, cwd, globs))
        base_tests = set(test_files_at(base_rev, cwd, globs))

        for rel in sorted(head_tests - base_tests):
            target = tree / rel
            if target.exists():
                target.unlink()

        if base_tests:
            # checkout from the base revision inside the worktree, then reset
            # the index so the overlay does not look like a staged change.
            git("checkout", base_rev, "--", *sorted(base_tests), cwd=tree)
            git("reset", "--quiet", cwd=tree, check=False)

        yield tree
