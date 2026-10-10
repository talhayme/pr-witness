"""Git plumbing, against real repositories rather than mocks.

Mocking git here would test my assumptions about git rather than git.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from pr_witness import git_ops


def commit(repo: Path, message: str, files: dict[str, str | None]) -> str:
    for rel, body in files.items():
        path = repo / rel
        if body is None:
            path.unlink(missing_ok=True)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=e@x", "-c", "user.name=n", "commit", "-qm", message],
        cwd=repo, check=True,
    )
    return git_ops.resolve("HEAD", cwd=repo)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(r)], check=True)
    return r


def test_test_files_are_found_by_the_default_globs(repo):
    commit(repo, "init", {
        "src/app.py": "x = 1\n",
        "tests/test_app.py": "def test_x(): pass\n",
        "src/widget.test.ts": "it('x', () => {})\n",
        "conftest.py": "",
        "README.md": "not a test\n",
    })
    found = git_ops.test_files_at("HEAD", repo)
    assert "tests/test_app.py" in found
    assert "src/widget.test.ts" in found
    assert "conftest.py" in found
    assert "src/app.py" not in found
    assert "README.md" not in found


def test_merge_base_ignores_commits_made_on_main_since_the_branch_started(repo):
    """Otherwise a long-running branch is blamed for everyone else's work."""
    first = commit(repo, "init", {"a.py": "1\n"})
    subprocess.run(["git", "checkout", "-q", "-b", "feature"], cwd=repo, check=True)
    head = commit(repo, "feature work", {"b.py": "2\n"})
    subprocess.run(["git", "checkout", "-q", "main"], cwd=repo, check=True)
    commit(repo, "unrelated work on main", {"c.py": "3\n"})

    assert git_ops.merge_base("main", head, cwd=repo) == first


def test_worktree_is_created_and_removed(repo):
    sha = commit(repo, "init", {"a.py": "1\n"})
    with git_ops.worktree(sha, repo) as tree:
        assert (tree / "a.py").read_text() == "1\n"
        created = tree
    assert not created.exists()


def test_the_users_checkout_is_never_modified(repo):
    """A tool that leaves your working copy dirty will not be run twice."""
    commit(repo, "init", {"src/a.py": "old\n", "tests/test_a.py": "def test(): pass\n"})
    base = git_ops.resolve("HEAD", cwd=repo)
    head = commit(repo, "change", {"src/a.py": "new\n", "tests/test_a.py": "def test(): assert 1\n"})

    with git_ops.crossrun_tree(base, head, repo):
        pass

    assert (repo / "src/a.py").read_text() == "new\n"
    assert git_ops.git("status", "--porcelain", cwd=repo) == ""


def test_crossrun_tree_pairs_head_code_with_base_tests(repo):
    commit(repo, "init", {
        "src/a.py": "VALUE = 'old'\n",
        "tests/test_a.py": "BASE_TEST = True\n",
    })
    base = git_ops.resolve("HEAD", cwd=repo)
    head = commit(repo, "change both", {
        "src/a.py": "VALUE = 'new'\n",
        "tests/test_a.py": "HEAD_TEST = True\n",
    })

    with git_ops.crossrun_tree(base, head, repo) as tree:
        assert (tree / "src/a.py").read_text() == "VALUE = 'new'\n"
        assert (tree / "tests/test_a.py").read_text() == "BASE_TEST = True\n"


def test_tests_added_by_the_pull_request_are_removed_from_the_crossrun(repo):
    """The cross-run must reproduce the base suite exactly, not approximately."""
    commit(repo, "init", {"src/a.py": "x = 1\n", "tests/test_old.py": "def test(): pass\n"})
    base = git_ops.resolve("HEAD", cwd=repo)
    head = commit(repo, "add a test", {"tests/test_new.py": "def test(): pass\n"})

    with git_ops.crossrun_tree(base, head, repo) as tree:
        assert (tree / "tests/test_old.py").exists()
        assert not (tree / "tests/test_new.py").exists()
