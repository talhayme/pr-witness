# Batch 1 — a measurement, written down before it is run

The first seven SWE-chat cases were picked by eye, and the tool was changed
after almost every one of them. A score from that is a score on cases the
tool was fitted to. This batch is the opposite: selected by rule, labelled
before running, run with the tool frozen.

**Frozen.** `src/` at commit `5570965` (tree `c7a30c52`). Nothing under
`src/pr_witness` changes until every case has run. The harness
(`eval/run_real.py`), the sandbox image and the install lines in the labels
may change — getting a stranger's project to install is not the tool.

**Selection.** `prepare_batch.py`, rule in its docstring: ranked candidates,
repositories already in the corpus excluded, Python tests under `tests/` or
JS/TS `*.test`/`*.spec` outside monorepo directories, at most 25 files and
300 changed test lines, at most five per class, one commit per repository,
and a repository that can plausibly be installed in the sandbox. 36 looked
at, 17 taken — the rule ran out before the target of 20.
`batch1_selection.json` records every candidate considered and why it was
left. (`osabio` is the renamed `brain`, already in the corpus under its old
name; the rule is mechanical and took it.)

**Labels.** Written from the diff, by the tool's author, before any run:
`verdict` is what the tool should say, `legitimacy` whether the edit looks
honest. The rubric:

- `flag` — a test disabled or weakened with no stated reason, guard tests
  deleted while the description says otherwise, a regression hidden from
  the pull request's own tests.
- `review` — an existing test's expectation rewritten; a deleted test whose
  behaviour is still there; a consolidation that drops a case.
- `clean` — tests added; tests removed together with what they tested; a
  refactor of the tests (rename, move, parametrise, literal → constant)
  that asserts the same things.

Seventeen labels: ten `clean`, seven `review`, no `flag`. Nothing in this
batch reads as dishonest. The rule's size limit is the likely reason — the
commits most worth suspecting are the large ones it leaves out.

**What will be reported.** For each case: ran or not (and why not), the
tool's verdict against the label, and for every disagreement whether it is
the label, the environment, or the tool — and if the tool, what would have
to change. The count of that last kind is the number this batch exists for.
