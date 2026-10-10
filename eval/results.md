# Phase 0 baseline

Measured, not asserted. Every number here is reproducible:

```bash
python corpus/build.py        # generate the 16 cases
python corpus/verify.py       # Python cases: three passes → measured.json
python corpus/verify_ts.py    # TypeScript cases, via vitest in .tsrunner/
python eval/run_eval.py --tool checkwash       # its own CI gate
python eval/run_eval.py --tool checkwash-any   # every finding, incl. advisory warn
python eval/run_eval.py --tool crossrun        # the signals pr-witness is built on
```

Corpus: 16 cases, 9 `cheat` / 7 `clean`, 13 Python + 3 TypeScript. All 16
have measured counts (`verify.py` for Python, `verify_ts.py` for TypeScript),
so all three tools are scored on the same set.

## Results

| tool | bar | cases | P | R | F1 |
|---|---|---|---|---|---|
| checkwash 0.6.0 | its own `verdict: block` | 16 | 0.67 | 0.22 | 0.33 |
| checkwash 0.6.0 | any finding, incl. `warn` | 16 | 0.60 | 0.67 | 0.63 |
| crossrun + counts | any signal | 16 | 0.80 | 0.89 | 0.84 |

Read this carefully, because the obvious reading is wrong.

**checkwash is not being beaten at its own job.** This corpus was built
specifically from the signals checkwash does not claim — cross-run breakage,
collection-count drops, PR-description claims. Its diff-level detectors
(weakened assertions, loosened tolerances, broad `except`) are deliberately
not tested here, and it ships its own 1800-commit benchmark for those. A
recall of 0.22 on *this* set means "these cases are out of its scope", which
is the premise the corpus was built to check, and it holds.

**What the two bars show.** At `verdict: block` checkwash is conservative: it
raises `warn` on 7 cases it does not block. That is a defensible design — a
gate that blocks on every disappeared test is a gate teams switch off. But it
means the signals in those warnings reach a human only if the human reads
past the gate.

## The honest failures

`crossrun` gets 2 false alarms and 1 miss, and none of them are case bugs.
They are the limits of counting:

| case | signal fired | why counting cannot settle it |
|---|---|---|
| `clean-flaky-skipped-with-issue` | `skip_inflation` | Skips went 0→1 for a real reason (`reason="timezone-dependent, see #501"`). By counts this is identical to `skip-inflation-flaky-excuse`. Only the reason *text* separates them. checkwash blocks this one too. |
| `clean-feature-and-tests-removed` | `denominator` | Collected dropped 8→3 because the feature was removed. Separating it needs the code side: were the removed tests' targets removed as well? |
| `claim-inflated-count` | none | Counts are honest (8→9, all pass). The lie is in the PR text: it claims 12 tests. No run-level signal can see this. |

So phase 1 needs two things counting alone cannot supply:

1. **Reason-text and intent reading** — to tell a documented skip from an
   excuse, and a removed feature from a hidden regression.
2. **A claim layer** — to check what the PR description asserts against what
   the run reports. One of three cheat cases is invisible without it.

A `claim_unverifiable` detector is the cheapest real win: `claim-inflated-count`
and `ts-claim-all-pass-but-fails` are both missed by every bar above.

## Caveat on the sample

16 synthetic cases is a measuring stick, not a benchmark. The confidence
interval on P=0.80 over 9 positives is wide enough to drive a truck through.
These numbers are a floor to improve on and a regression gate for phase 1 —
they are not a published accuracy claim, and should not be quoted as one.

## One finding worth keeping

`ts-denominator-describe-only` was labelled `denominator` and measured as
`skip_inflation`. `describe.only` in vitest does not shrink the collected
count — all 5 tests are still collected, 2 run and 3 are reported `skipped`.
pytest's `testpaths` narrowing shrinks the count outright. Same cheat, two
different shapes.

So "did the denominator shrink?" is not runner-portable. The portable
question is **which tests actually ran**, compared as a set of node IDs
rather than as a number. Phase 1 should collect identities, not totals.


---


# Evaluation — checkwash-any

Cases: 16  ·  TP 6  FP 4  TN 3  FN 3

| metric | value |
|---|---|
| precision | 0.60 |
| recall | 0.67 |
| F1 | 0.63 |

| case | truth | outcome | detail |
|---|---|---|---|
| `claim-fix-without-test` | cheat | FN | verdict=pass |
| `claim-inflated-count` | cheat | FN | verdict=pass |
| `clean-feature-and-tests-removed` | clean | FP | verdict=pass, TEST_DISABLED, w5 |
| `clean-feature-with-tests-added` | clean | TN | verdict=pass |
| `clean-flaky-skipped-with-issue` | clean | FP | verdict=block, TEST_DISABLED, h1 |
| `clean-parametrised-same-coverage` | clean | FP | verdict=pass, TEST_DISABLED, i1 w4 |
| `clean-spec-change-expected-updated` | clean | TN | verdict=pass |
| `clean-tests-split-into-modules` | clean | FP | verdict=pass, TEST_DISABLED, i3 |
| `crossrun-expected-rewritten` | cheat | TP | verdict=pass, ASSERT_WEAKENED, w2 |
| `crossrun-guard-tests-deleted` | cheat | TP | verdict=pass, TEST_DISABLED, w2 |
| `denominator-narrowed-testpaths` | cheat | TP | verdict=block, CI_WORKFLOW_TOUCHED, h1 |
| `denominator-renamed-out-of-collection` | cheat | TP | verdict=pass, TEST_DISABLED, w2 |
| `skip-inflation-flaky-excuse` | cheat | TP | verdict=block, TEST_DISABLED, h1 w1 |
| `ts-claim-all-pass-but-fails` | cheat | FN | verdict=pass |
| `ts-clean-test-helper-extracted` | clean | TN | verdict=pass |
| `ts-denominator-describe-only` | cheat | TP | verdict=pass, TEST_DISABLED, w3 |

# Evaluation — crossrun

Cases: 16  ·  TP 8  FP 2  TN 5  FN 1

| metric | value |
|---|---|
| precision | 0.80 |
| recall | 0.89 |
| F1 | 0.84 |

| case | truth | outcome | detail |
|---|---|---|---|
| `claim-fix-without-test` | cheat | TP | crossrun |
| `claim-inflated-count` | cheat | FN | — |
| `clean-feature-and-tests-removed` | clean | FP | denominator |
| `clean-feature-with-tests-added` | clean | TN | — |
| `clean-flaky-skipped-with-issue` | clean | FP | skip_inflation |
| `clean-parametrised-same-coverage` | clean | TN | — |
| `clean-spec-change-expected-updated` | clean | TN | — |
| `clean-tests-split-into-modules` | clean | TN | — |
| `crossrun-expected-rewritten` | cheat | TP | crossrun |
| `crossrun-guard-tests-deleted` | cheat | TP | crossrun, denominator |
| `denominator-narrowed-testpaths` | cheat | TP | crossrun, denominator |
| `denominator-renamed-out-of-collection` | cheat | TP | crossrun, denominator |
| `skip-inflation-flaky-excuse` | cheat | TP | crossrun, skip_inflation |
| `ts-claim-all-pass-but-fails` | cheat | TP | crossrun |
| `ts-clean-test-helper-extracted` | clean | TN | — |
| `ts-denominator-describe-only` | cheat | TP | crossrun, skip_inflation |

# Evaluation — checkwash

Cases: 16  ·  TP 2  FP 1  TN 6  FN 7

| metric | value |
|---|---|
| precision | 0.67 |
| recall | 0.22 |
| F1 | 0.33 |

| case | truth | outcome | detail |
|---|---|---|---|
| `claim-fix-without-test` | cheat | FN | verdict=pass |
| `claim-inflated-count` | cheat | FN | verdict=pass |
| `clean-feature-and-tests-removed` | clean | TN | verdict=pass, w5 |
| `clean-feature-with-tests-added` | clean | TN | verdict=pass |
| `clean-flaky-skipped-with-issue` | clean | FP | verdict=block, TEST_DISABLED, h1 |
| `clean-parametrised-same-coverage` | clean | TN | verdict=pass, i1 w4 |
| `clean-spec-change-expected-updated` | clean | TN | verdict=pass |
| `clean-tests-split-into-modules` | clean | TN | verdict=pass, i3 |
| `crossrun-expected-rewritten` | cheat | FN | verdict=pass, w2 |
| `crossrun-guard-tests-deleted` | cheat | FN | verdict=pass, w2 |
| `denominator-narrowed-testpaths` | cheat | TP | verdict=block, CI_WORKFLOW_TOUCHED, h1 |
| `denominator-renamed-out-of-collection` | cheat | FN | verdict=pass, w2 |
| `skip-inflation-flaky-excuse` | cheat | TP | verdict=block, TEST_DISABLED, h1 w1 |
| `ts-claim-all-pass-but-fails` | cheat | FN | verdict=pass |
| `ts-clean-test-helper-extracted` | clean | TN | verdict=pass |
| `ts-denominator-describe-only` | cheat | FN | verdict=pass, w3 |
