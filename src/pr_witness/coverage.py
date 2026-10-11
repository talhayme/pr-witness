"""Replacement: the one test edit the cross-run cannot see.

A pull request deletes the tests that exercised a function, removes a helper
those tests also imported, and adds different tests. The old test file no
longer loads against the new code — which is exactly what honest cleanup
looks like, so every run the tool can do comes out consistent with "the
subject was removed". But the function is still there, and nothing calls it
any more.

Runs cannot tell these apart; reading can. For each test file the change
touched, this asks three questions of the source:

  1. which functions from the repository did the old tests call for real
     (not merely inside a `pytest.raises` block)?
  2. which of those still exist after the change?
  3. does any test still call them for real?

A function that was called, still exists and is no longer called is
reported, at review level: a human reads the diff. It is a reading by name.
It cannot see a call made indirectly, through another function, and says so.
Python only.
"""

from __future__ import annotations

import ast
from pathlib import PurePosixPath

from pr_witness import git_ops
from pr_witness.compare import Finding, Severity

# A test that expects an error calls the function without checking what it
# does. `with pytest.raises(...)`, `with self.assertRaises(...)`.
_RAISES = ("raises", "assertRaises", "assertRaisesRegex", "assertRaisesRegexp")
_MAX_SOURCE = 1_500_000        # bytes; larger files are skipped, not guessed at
_MAX_CANDIDATES = 300          # head test files read per symbol before assuming "still called"


def _is_test(path: str, globs) -> bool:
    return any(git_ops.matches_glob(path, g) for g in globs)


def _source(repo, rev: str, path: str) -> str | None:
    try:
        text = git_ops.git("show", f"{rev}:{path}", cwd=repo, check=False)
    except Exception:  # noqa: BLE001
        return None
    return text if text and len(text) <= _MAX_SOURCE else None


def _parse(text: str | None) -> ast.AST | None:
    if not text:
        return None
    try:
        return ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return None


def _resolve(module: str, level: int, importer: str, files: set[str]) -> str | None:
    """A dotted module name → the repository file that defines it, if any."""
    if level:
        base = PurePosixPath(importer).parent
        for _ in range(level - 1):
            base = base.parent
        stem = str(base / module.replace(".", "/")) if module else str(base)
        for cand in (stem + ".py", stem + "/__init__.py"):
            if cand in files:
                return cand
        return None
    if not module:
        return None
    tail = module.replace(".", "/")
    hits = [f for f in files
            if f == tail + ".py" or f.endswith("/" + tail + ".py")
            or f == tail + "/__init__.py" or f.endswith("/" + tail + "/__init__.py")]
    return min(hits, key=len) if hits else None


def _dotted(node: ast.AST) -> list[str] | None:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return parts[::-1]
    return None


def _opens_raises(node: ast.AST) -> bool:
    if not isinstance(node, (ast.With, ast.AsyncWith)):
        return False
    for item in node.items:
        call = item.context_expr
        if isinstance(call, ast.Call):
            name = _dotted(call.func)
            if name and name[-1] in _RAISES:
                return True
    return False


def _calls(tree: ast.AST):
    """Every call in the tree as (dotted name parts, inside a raises block?)."""
    def walk(node: ast.AST, in_raises: bool):
        if isinstance(node, ast.Call):
            name = _dotted(node.func)
            if name:
                yield name, in_raises
        if _opens_raises(node):
            for item in node.items:                      # the raises(...) call itself
                yield from walk(item, in_raises)
            for child in node.body:
                yield from walk(child, True)
            return
        for child in ast.iter_child_nodes(node):
            yield from walk(child, in_raises)
    yield from walk(tree, False)


def _imports(tree: ast.AST, path: str, files: set[str], globs):
    """Names this test file binds to repository code that is not itself a test.

    Returns (symbols, modules): local name → (file, name) for `from m import f`,
    and dotted alias → file for `import m` / `import m as x` / `from p import m`.
    """
    symbols: dict[str, tuple[str, str]] = {}
    modules: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    continue
                local = alias.asname or alias.name
                sub = _resolve(f"{node.module}.{alias.name}" if node.module else alias.name,
                               node.level, path, files)
                if sub and not _is_test(sub, globs):
                    modules[local] = sub
                    continue
                target = _resolve(node.module or "", node.level, path, files)
                if target and not _is_test(target, globs):
                    symbols[local] = (target, alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                target = _resolve(alias.name, 0, path, files)
                if target and not _is_test(target, globs):
                    modules[alias.asname or alias.name] = target
    return symbols, modules


def _called_for_real(tree: ast.AST, path: str, files: set[str], globs) -> set[tuple[str, str]]:
    symbols, modules = _imports(tree, path, files, globs)
    out: set[tuple[str, str]] = set()
    for parts, in_raises in _calls(tree):
        if in_raises:
            continue
        if parts[0] in symbols:
            out.add(symbols[parts[0]])
            continue
        for k in range(len(parts) - 1, 0, -1):
            alias = ".".join(parts[:k])
            if alias in modules:
                out.add((modules[alias], parts[k]))
                break
    return out


def _defines(tree: ast.AST, name: str) -> bool:
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
            return True
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return True
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return True
        if isinstance(node, (ast.ImportFrom, ast.Import)) and any((a.asname or a.name) == name for a in node.names):
            return True
    return False


def _use_in(tree: ast.AST, name: str) -> str:
    """How a test file uses `name`: 'real', 'raises' (only where an error is expected) or ''.

    Deliberately generous: any reference by that name outside a raises block
    counts as real, whatever it was imported from. Erring this way keeps a
    finding from firing on a function that is in fact still exercised.
    """
    seen_in_raises = False

    def walk(node: ast.AST, in_raises: bool) -> bool:
        nonlocal seen_in_raises
        hit = (isinstance(node, ast.Name) and node.id == name) or \
              (isinstance(node, ast.Attribute) and node.attr == name)
        if hit:
            if not in_raises:
                return True
            seen_in_raises = True
        if _opens_raises(node):
            return any(walk(i, in_raises) for i in node.items) or any(walk(c, True) for c in node.body)
        return any(walk(c, in_raises) for c in ast.iter_child_nodes(node))

    if walk(tree, False):
        return "real"
    return "raises" if seen_in_raises else ""


def detect_coverage_replaced(repo, base: str, head: str, changed_files, test_globs=None) -> list[Finding]:
    """Functions the changed tests used to call, that still exist, and that no test calls now."""
    globs = test_globs or git_ops.DEFAULT_TEST_GLOBS
    touched = [f for f in changed_files if f.endswith(".py") and _is_test(f, globs)]
    if not touched:
        return []
    try:
        base_files = set(git_ops.git("ls-tree", "-r", "--name-only", base, cwd=repo).splitlines())
        head_files = set(git_ops.git("ls-tree", "-r", "--name-only", head, cwd=repo).splitlines())
    except Exception:  # noqa: BLE001
        return []

    # 1. what the old versions of the touched test files called for real
    was_called: dict[tuple[str, str], set[str]] = {}
    for path in touched:
        if path not in base_files:
            continue
        tree = _parse(_source(repo, base, path))
        if tree is None:
            continue
        for symbol in _called_for_real(tree, path, base_files, globs):
            was_called.setdefault(symbol, set()).add(path)
    if not was_called:
        return []

    trees: dict[str, ast.AST | None] = {}

    def head_tree(path: str) -> ast.AST | None:
        if path not in trees:
            trees[path] = _parse(_source(repo, head, path))
        return trees[path]

    replaced: list[tuple[str, str, str]] = []
    for (module, name), callers in sorted(was_called.items()):
        # 2. still there?
        if module not in head_files:
            continue
        mod_tree = head_tree(module)
        if mod_tree is None or not _defines(mod_tree, name):
            continue
        # 3. still called by a test?
        try:
            hits = git_ops.git("grep", "-l", "-w", "-F", name, head, "--", "*.py", cwd=repo, check=False)
        except Exception:  # noqa: BLE001
            continue
        candidates = [h.split(":", 1)[-1] for h in hits.splitlines() if h.strip()]
        candidates = [c for c in candidates if _is_test(c, globs)]
        if len(candidates) > _MAX_CANDIDATES:
            continue                                     # a name that common is called somewhere
        use = ""
        for cand in candidates:
            tree = head_tree(cand)
            if tree is None:                             # unreadable: assume it is used
                use = "real"
                break
            found = _use_in(tree, name)
            if found == "real":
                use = "real"
                break
            use = use or found
        if use != "real":
            replaced.append((module, name, use))

    if not replaced:
        return []
    shown = ", ".join(
        f"`{name}`" + (" (now only where an error is expected)" if use == "raises" else "")
        for _, name, use in replaced[:6]
    ) + (" …" if len(replaced) > 6 else "")
    return [Finding(
        "coverage_replaced",
        Severity.MEDIUM,
        f"{len(replaced)} function(s) the changed tests used to call still exist, "
        f"and no test calls them for real any more: {shown}",
        "Legitimate when the function is exercised indirectly, through another "
        "function the remaining tests call, or in a suite this repository does "
        "not hold. This is a reading of the source by name; it cannot see an "
        "indirect call.",
        [f"{module}::{name}" for module, name, _ in replaced],
    )]
