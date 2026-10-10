# Evaluation — pr-witness (phase 3)

```bash
python eval/run_witness.py     # findings + claim verdicts
python eval/run_claims.py      # claim verdicts against the labels
```

## Where phase 3 landed

| | P | R | F1 |
|---|---|---|---|
| checkwash 0.6.0 (its own gate) | 0.67 | 0.22 | 0.33 |
| phase-0 baseline (raw counts) | 0.80 | 0.89 | 0.84 |
| phase 1 (cross-run + counters) | 0.89 | 0.89 | 0.89 |
| phase 2 (+ diff integrity) | 0.90 | 0.90 | 0.90 |
| **phase 3 (+ claim checking)** | **0.91** | **1.00** | **0.95** |

Recall 1.00: every dishonest case in the corpus is now caught. No honest
change received a `claim_false`.

Claim verdicts agree with the hand-written labels on **18 of 19** claims
(0.95). The 19th is discussed below.

## The case that needed this phase

`claim-inflated-count` was missed by phases 0, 1 and 2 alike. The run is
entirely honest — 8 tests before, 9 after, all green, nothing skipped, the
cross-run clean. The lie lives only in the prose:

> Added 41 tests for the discount logic. 49/49 passing.

```
verdict: flag
findings: none
  false  "49/49 passing"   — the run reports 9 passed
  false  "Added 41 tests"  — the run shows 1 new test, not 41
```

No run-level or diff-level signal can see this. It is also, per the plan's
source research, one of the commonest real-world shapes.

## What "misleading" is for, and why it earns its place

The hardest verdicts were not the lies. They were the sentences that are
literally true and leave a false impression:

| Case | Claim | Run says | Verdict |
|---|---|---|---|
| `denominator-narrowed-testpaths` | "8 tests pass" | exactly 8 pass | **misleading** — the base branch ran 14 |
| `crossrun-expected-rewritten` | "All tests pass" | all 6 pass | **misleading** — a base test fails on this code |
| `ts-broad-catch` | "All tests pass" | 3/3 on every run | **misleading** — an assertion was neutralised |
| `skip-inflation-flaky-excuse` | "8 passed" | 8 collected, 6 passed | **misleading** — the number is real, the line is wrong |

A checker that called these `true` would be trivially gameable: narrow the
suite, then quote the smaller number truthfully. One that called them
`false` would be accusing authors of lying when they quoted their own
terminal correctly. `misleading` is the honest third answer, and getting
these four right took three separate fixes:

1. **Judge a green claim against the base denominator**, not against itself
   (0.74 → 0.84).
2. **A number from the wrong line of the summary** — `collected` quoted as
   `passed` — is inaccuracy, not invention. But only when nothing actually
   failed: a green number over a red run stays `false` (0.84 → 0.95).
3. **Temper a green claim with diff evidence.** `ts-broad-catch` reports
   3 collected / 3 passed on all three runs; only the `broad_catch` finding
   knows the assertion was neutralised. This is the three layers finally
   working together — the run says green, the diff says hollow, the claim
   checker says misleading.

## What is deliberately not checked

`Fixes #318` is reported `unverifiable`, not guessed at. Whether a change
fixes an issue is not something a test run can answer, and inventing a
heuristic for it would produce confident nonsense in both directions.

"Added tests for `parse_date`" with no new test naming `parse_date` is
`misleading`, never `false`: the absence of a name is weak evidence, since
the behaviour may be covered indirectly.

No LLM is involved. The plan allows one for extracting claims from free
prose (§8, off by default) and it is not implemented yet; a model that
hallucinated a claim the author never made would be worse than no claim
checking at all.

## The remaining false alarm

`clean-feature-and-tests-removed`, unchanged since phase 1: a feature was
removed with its tests, and the cross-run cannot confirm the removed tests
because they no longer compile — which is exactly what honest removal looks
like. Separating it from a hidden regression needs code-side analysis of
whether the removed tests' *targets* also went away.

Notably, its claims are all judged correctly ("3 tests remain" → true). The
false alarm comes from the run-level signals, not from this phase.

## Caveat, unchanged

17 synthetic cases, 19 labelled claims. R=1.00 over 10 positives means "no
misses in this corpus", not "no misses". The honest reading is that the
corpus no longer discriminates between phases — it needs harder cases more
than the tool needs more detectors.

---

# Evaluation — pr-witness (phase 1)

Cases: 17  ·  TP 10  FP 1  TN 6  FN 0

| metric | value |
|---|---|
| precision | 0.91 |
| recall | 1.00 |
| F1 | 0.95 |

| case | truth | outcome | signals |
|---|---|---|---|
| `claim-fix-without-test` | cheat | TP | crossrun, claim_false(Added test) |
| `claim-inflated-count` | cheat | TP | claim_false(49/49 passing), claim_false(Added 41 tests) |
| `clean-feature-and-tests-removed` | clean | FP | crossrun_vanished, denominator_removed, (checkwash:TEST_DISABLED), (checkwash:TEST_DISABLED), (checkwash:TEST_DISABLED), (checkwash:TEST_DISABLED), (checkwash:TEST_DISABLED) |
| `clean-feature-with-tests-added` | clean | TN | — |
| `clean-flaky-skipped-with-issue` | clean | TN | (checkwash:TEST_DISABLED), (skip_documented) |
| `clean-parametrised-same-coverage` | clean | TN | (checkwash:TEST_DISABLED), (checkwash:TEST_DISABLED), (checkwash:TEST_DISABLED), (checkwash:TEST_DISABLED), (checkwash:TEST_DISABLED) |
| `clean-spec-change-expected-updated` | clean | TN | — |
| `clean-tests-split-into-modules` | clean | TN | (checkwash:TEST_DISABLED), (checkwash:TEST_DISABLED), (checkwash:TEST_DISABLED) |
| `crossrun-expected-rewritten` | cheat | TP | crossrun, (checkwash:ASSERT_WEAKENED), (checkwash:ASSERT_WEAKENED), (claim_misleading(All tests pass)) |
| `crossrun-guard-tests-deleted` | cheat | TP | crossrun, denominator_removed, claim_false(No breaking changes), (checkwash:TEST_DISABLED), (checkwash:TEST_DISABLED) |
| `denominator-narrowed-testpaths` | cheat | TP | checkwash:CI_WORKFLOW_TOUCHED, crossrun, denominator_removed, (claim_misleading(8 tests pass)) |
| `denominator-renamed-out-of-collection` | cheat | TP | crossrun, denominator_removed, (checkwash:TEST_DISABLED), (checkwash:TEST_DISABLED), (claim_misleading(Tests green)) |
| `skip-inflation-flaky-excuse` | cheat | TP | checkwash:TEST_DISABLED, crossrun, denominator, skip_inflation, (checkwash:TEST_DISABLED), (claim_misleading(8 passed)) |
| `ts-broad-catch` | cheat | TP | broad_catch, (claim_misleading(All tests pass)) |
| `ts-claim-all-pass-but-fails` | cheat | TP | crossrun, claim_false(5 tests pass) |
| `ts-clean-test-helper-extracted` | clean | TN | — |
| `ts-denominator-describe-only` | cheat | TP | crossrun, denominator, skip_inflation, (checkwash:TEST_DISABLED), (checkwash:TEST_DISABLED), (checkwash:TEST_DISABLED), (claim_misleading(Suite is green)) |
