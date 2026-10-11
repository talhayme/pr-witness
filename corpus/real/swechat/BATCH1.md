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

---

# Results (2026-10-11)

All seventeen were attempted, one at a time, in the sandbox; thirteen
minutes in total. `src/` was not touched (tree `c7a30c52` before and after).
Two harness changes were made along the way and are not the tool: a failed
install now fails the sandbox stage instead of letting the run report
"pytest not found" as a finding, and two cases had their install lines
corrected and were rerun once.

## What ran

| | cases |
|---|---|
| produced evidence (some base test passed, comparison meaningful) | **12** |
| ran, but vacuously — every test skipped or uncollectable without the services the suite needs | 4 (bids-utils, chaoswopr, agentcenter-nuxt, pc-switcher) |
| could not be installed | 1 (lock-code-manager: a C extension with no wheel for the sandbox's Python) |

The four vacuous runs are not counted for or against the tool. Two of them
"matched" their label and one did not; none of that is evidence.

## The twelve

| case | label | tool | |
|---|---|---|---|
| uv-script | review | review | ✓ `greened_by_test_edit` ×12 — 21 of 61 tests were red on base |
| pydantic2linkml | review | review | ✓ `tests_removed_still_passing` — though it lists all five deleted tests, three of which were folded into the parametrised one |
| mastra-slack-agent | clean | note | ✓ `tests_removed_subject_gone` |
| hevy-planner | review | review | ✓ `expectation_changed` |
| osabio | clean | clean | ✓ old tests pass on new code: literal → constant |
| context-evaluator | review | review | ✓ `expectation_changed` ×2 |
| my-first-commit | clean | clean | ✓ — but see T5 |
| authsome | review | **note** | ✗ T1 |
| optimize-anything | clean | **flag** | ✗ T2 |
| sound-map | clean | **flag** | ✗ T3 |
| agent-tail | review | **flag** | ✗ T3 — `expectation_changed` ×3 is there; the flag is from elsewhere |
| langlearn-tts | review | **flag** | ✗ T4 |

**Seven of twelve.** None of the five disagreements is a label I would
change on reflection, and none is the environment. All five are the tool.

## What would have to change

- **T1 — pytest stops at the first file that fails to import.** authsome's
  refactor removed classes that two of ten old test files imported; pytest
  aborted the whole cross-run session, all 76 base tests "vanished", and the
  rewritten expectations in the eight files that still load were never run.
  `--continue-on-collection-errors` is the fix. An under-call: `note` where
  a human should have been shown the rewritten assertions.
- **T2 — a new test that is skipped is not skip inflation.** The check is
  `head.skipped − base.skipped`, which includes tests that did not exist on
  base. Three new integration tests guarded by `skipif(..., reason="OPENAI_API_KEY
  required")` were reported as tests hidden without a reason: a `flag` on a
  commit that only added tests. Two faults in one: "required" is not in the
  external-cause vocabulary ("requires" is), and a skipped *new* test hides
  nothing — it should be reported as added-but-not-run, not as a flag.
  (The vacuous chaoswopr run flags for the same reason.)
- **T3 — editing CLAUDE.md is a flag.** checkwash rates a change to an agent
  instruction file high, and pr-witness passes its highs through. In a
  repository developed with an agent that file is edited all the time: two
  of twelve honest commits were flagged for a two-line documentation edit
  and nothing else. Whether this should be a note or a review is a policy
  decision; a flag is wrong.
- **T4 — checkwash's other rewrite rules.** An honest change of a default
  value produced twelve highs from rules the reconciliation does not know —
  `ASSERT_SUBSTITUTED`, `EXPECTED_VALUE_HARDCODED`, `SUBJECT_INPUT_CHANGED` —
  and the run could not corroborate them, because the old conftest's mocks
  keep the old tests passing against the new code. A rewritten expectation
  is a `review` by this tool's own definition; that should hold for every
  static rule that says "the expectation was rewritten", corroborated or not.
- **T5 — latent, changed no verdict.** When a restricted path does not exist
  on the base branch, the base run falls back to the whole suite (106 tests
  against the head's 7). It should run nothing.

## What this says

**The tool has not settled.** Five of twelve cases would change it, four
distinct ways — the same rate as the seven hand-picked cases before it. The
6/7 in the README is a number on cases the tool was fitted to; on cases it
had never seen it is 7/12.

**Its failures on honest commits are loud ones.** Four of twelve were
flagged, and all four are honest. Nothing here was labelled `flag`, so the
tool's `flag` was wrong every time it was used. `review` was right four
times out of four.

**It says nothing yet about catching dishonesty.** No commit in this batch
reads as a cheat, so recall on real data is still unmeasured. The size
limit in the selection rule is the likely reason, and a batch aimed at the
largest-ranked commits is the way to find out.

Evidence files for every case are in the local cache
(`~/.cache/pr-witness-real/swechat/evidence/`); verdicts and counts are in
`eval/real_results_swechat.json`.

---

# After the batch (0.3.1)

T1–T4 are fixed in 0.3.1, each with a test that names the case it came from:

- **T1** — pytest runs with `--continue-on-collection-errors`.
- **T2** — a skipped test the pull request added is `added_tests_skipped`
  (low), not skip inflation; "required", "api key", "credentials", "not
  running", "unreachable" join the external-cause vocabulary.
- **T3** — checkwash `GUARDRAIL_TOUCHED` is reported at medium: a note in
  the report, not a flag and not a review.
- **T4** — checkwash's rewrite rules (`EXPECTED_VALUE_CHANGED`,
  `ASSERT_SUBSTITUTED`, `EXPECTED_VALUE_HARDCODED`, `SUBJECT_INPUT_CHANGED`)
  are a review whether or not a run corroborates them. The weakening rules
  (`ASSERT_REMOVED`, `ASSERT_WEAKENED`, `BROAD_EXCEPT_ADDED`, …) keep
  checkwash's rating.

T5 is not fixed. Neither is the over-count in `tests_removed_still_passing`.

With the fixes, the five disagreements above become agreements and the
seven agreements stay — twelve of twelve. **That is not a result.** It is
the tool agreeing with the cases it was just changed to agree with, and it
is recorded here only so that nobody, the author included, mistakes it for
one. The measurement is the 7/12 above. The next measurement needs commits
this tool has never been run on.

The same fixed tool was rerun on every earlier real case as a regression
check: the six SWE-bench cases and six of the first seven SWE-chat cases
keep their verdicts; hypergraph is still the one miss there (a broad
`except` in a test file — a weakening rule, deliberately left at
checkwash's rating).

