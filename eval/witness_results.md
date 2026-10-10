# Evaluation — pr-witness (phase 1)

Run end to end on the corpus: every case becomes a real two-commit git
repository, and the tool does the real thing — three worktrees, three runner
invocations, three JUnit reports. Nothing here reads `measured.json`; this
measures the tool, not the fixture.

```bash
python eval/run_witness.py
```

## Where phase 1 landed

| tool | P | R | F1 |
|---|---|---|---|
| checkwash 0.6.0 (its own gate) | 0.67 | 0.22 | 0.33 |
| phase-0 baseline (raw counts) | 0.80 | 0.89 | 0.84 |
| **pr-witness 0.1.0** | **0.89** | **0.89** | **0.89** |

Above the plan's 0.8 precision floor. The gain over the raw-count baseline is
entirely in precision — two honest refactors the counting signals flagged,
the tool now clears.

## The two things that moved precision

**Renames and splits are not deletions.** The first working version scored
P 0.67, *worse* than the baseline it was meant to improve on. Comparing test
identities means a renamed file, a split module and a parametrised collapse
each delete every identity they touch while changing no coverage at all —
three of the commonest honest refactors there are, all flagged.

The fix is to let the cross-run settle it: if the behaviour really is still
covered, the base branch's own tests still pass against the new code. A
vanished identity is only worth reporting when the cross-run cannot confirm
it. That alone took precision 0.67 → 0.80 without costing a single detection.

**A documented skip was being reported twice** — correctly as
`skip_documented` (INFO) and wrongly as `denominator` (HIGH), because a
skipped test is by definition collected-but-not-running. 0.80 → 0.89.

Both bugs are the same mistake in different clothes: a signal that is
technically true and practically useless. Precision is not a number you tune
at the end; it is whether the tool is worth reading.

## What is still wrong

| case | outcome | why |
|---|---|---|
| `clean-feature-and-tests-removed` | false alarm | A feature was removed along with its tests. The cross-run cannot confirm the removed tests because they no longer compile against the new code — which is exactly what honest removal looks like. Separating this from a hidden regression needs the code side: were the removed tests' *targets* also removed? That is phase 2. |
| `claim-inflated-count` | missed | Counts are honest (8→9, all green). The PR text claims 12 tests. No run-level signal can see a lie that lives only in prose. Phase 3. |

Both failures are the ones phase 0 predicted, which is mildly reassuring
about the corpus.

## Caveat, unchanged from phase 0

16 synthetic cases. P=0.89 over 9 positives has a confidence interval wide
enough to drive a truck through. These numbers are a regression gate for
phase 2, not a published accuracy claim.

---

# Evaluation — pr-witness (phase 1)

Cases: 16  ·  TP 8  FP 1  TN 6  FN 1

| metric | value |
|---|---|
| precision | 0.89 |
| recall | 0.89 |
| F1 | 0.89 |

| case | truth | outcome | signals |
|---|---|---|---|
| `claim-fix-without-test` | cheat | TP | crossrun |
| `claim-inflated-count` | cheat | FN | — |
| `clean-feature-and-tests-removed` | clean | FP | crossrun_vanished, denominator_removed |
| `clean-feature-with-tests-added` | clean | TN | — |
| `clean-flaky-skipped-with-issue` | clean | TN | (skip_documented) |
| `clean-parametrised-same-coverage` | clean | TN | — |
| `clean-spec-change-expected-updated` | clean | TN | — |
| `clean-tests-split-into-modules` | clean | TN | — |
| `crossrun-expected-rewritten` | cheat | TP | crossrun |
| `crossrun-guard-tests-deleted` | cheat | TP | crossrun, denominator_removed |
| `denominator-narrowed-testpaths` | cheat | TP | crossrun, denominator_removed |
| `denominator-renamed-out-of-collection` | cheat | TP | crossrun, denominator_removed |
| `skip-inflation-flaky-excuse` | cheat | TP | crossrun, denominator, skip_inflation |
| `ts-claim-all-pass-but-fails` | cheat | TP | crossrun |
| `ts-clean-test-helper-extracted` | clean | TN | — |
| `ts-denominator-describe-only` | cheat | TP | crossrun, denominator, skip_inflation |
