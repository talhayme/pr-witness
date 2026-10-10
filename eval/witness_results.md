# Evaluation — pr-witness (phase 2)

Run end to end: every case becomes a real two-commit git repository, and the
tool does the real thing — three worktrees, three runner invocations, three
JUnit reports, plus checkwash and the JS/TS gap detectors.

```bash
python eval/run_witness.py
```

## Where phase 2 landed

| | P | R | F1 | cases |
|---|---|---|---|---|
| checkwash 0.6.0 (its own gate) | 0.67 | 0.22 | 0.33 | 16 |
| phase-0 baseline (raw counts) | 0.80 | 0.89 | 0.84 | 16 |
| phase 1 (cross-run + counters) | 0.89 | 0.89 | 0.89 | 16 |
| **phase 2 (+ diff integrity)** | **0.90** | **0.90** | **0.90** | 17 |

The headline number barely moved, and that is the honest summary: phase 2
added a whole class of detection without improving the score, because the
corpus had almost no cases only a diff can catch. So one was added —
`ts-broad-catch`, where **all three runs report 3 collected, 3 passed**. No
run-level signal can see it. That case is the entire argument for this phase.

## What the plan assumed, and what was true

The plan was written against checkwash v0.5 and listed ten JS/TS patterns to
implement. Measured against 0.6.0, seven were already covered:

| Pattern | checkwash 0.6.0 |
|---|---|
| `expect(...)` removed | ✅ `ASSERT_REMOVED` |
| `.skip` / `xit` / `xdescribe` | ✅ `TEST_DISABLED` |
| `.only` narrowing the run | ✅ `TEST_DISABLED` |
| `toBeCloseTo` with reduced precision | ✅ `ASSERT_WEAKENED` |
| `expect.anything()` for a value | ✅ `ASSERT_WEAKENED` |
| `vi.mock` on the module under test | ✅ `TEST_PATCHES_SUBJECT` |
| CI `continue-on-error` / `\|\| true` | ✅ `CI_WORKFLOW_TOUCHED` |
| `try`/`catch` swallowing an assertion | ❌ implemented here |
| `@ts-ignore` on an asserting line | ❌ implemented here |
| `eslint-disable` of a test-quality rule | ❌ implemented here |

Writing the other seven would have been a week spent producing a worse copy
of working code. Each remaining gap is written up in
[`docs/upstream/`](../docs/upstream/) as a proposal to checkwash first, per
the plan's rule — **none have been sent yet; they need your approval.**

## The precision scare, and what it taught

Integrating checkwash dropped precision from 0.90 to **0.75**, below the
plan's floor. Cause: I mapped its `warn` findings to MEDIUM, making them
flags. But checkwash blocks only on `high` — it raises `warn` for every
disappeared test, so every honest rename and module split produced a
handful. Mapping `warn` to LOW restored 0.82.

The remaining gap was one real disagreement. checkwash blocks on **any**
added skip marker, whatever its reason. pr-witness does not flag a skip whose
reason names a tracking issue.

Rather than silently discarding its finding, the report keeps it, downgrades
it to INFO, and states the disagreement:

> checkwash reports every added skip marker. pr-witness does not flag this
> one: the run shows a skip reason that names an issue. If your policy is
> that no skip is acceptable, trust checkwash here, not us.

That is the difference between integrating a tool and overruling it.

## Two bugs the tests caught

**The eslint detector never worked.** Its regex excluded `/` from the rule
list, so `vitest/expect-expect` was truncated to `vitest` and matched
nothing. It would have shipped as dead code that looked fine in review.

**A bare `/* eslint-disable */`** names no rules, which means all of them.
The first fix skipped it entirely.

## What is still wrong

| case | outcome | why |
|---|---|---|
| `clean-feature-and-tests-removed` | false alarm | A feature removed with its tests. The cross-run cannot confirm the removed tests because they no longer compile — which is what honest removal looks like. Needs code-side analysis: were the tests' *targets* also removed? |
| `claim-inflated-count` | missed | Counts are honest; the PR text claims 12 tests where there are 9. Invisible to every run-level and diff-level signal. **Phase 3.** |

## Caveat, unchanged

17 synthetic cases. P=0.90 over 10 positives has a wide confidence interval.
A regression gate for phase 3, not a published accuracy claim.

---

# Evaluation — pr-witness (phase 1)

Cases: 17  ·  TP 9  FP 1  TN 6  FN 1

| metric | value |
|---|---|
| precision | 0.90 |
| recall | 0.90 |
| F1 | 0.90 |

| case | truth | outcome | signals |
|---|---|---|---|
| `claim-fix-without-test` | cheat | TP | crossrun |
| `claim-inflated-count` | cheat | FN | — |
| `clean-feature-and-tests-removed` | clean | FP | crossrun_vanished, denominator_removed, (checkwash:TEST_DISABLED), (checkwash:TEST_DISABLED), (checkwash:TEST_DISABLED), (checkwash:TEST_DISABLED), (checkwash:TEST_DISABLED) |
| `clean-feature-with-tests-added` | clean | TN | — |
| `clean-flaky-skipped-with-issue` | clean | TN | (checkwash:TEST_DISABLED), (skip_documented) |
| `clean-parametrised-same-coverage` | clean | TN | (checkwash:TEST_DISABLED), (checkwash:TEST_DISABLED), (checkwash:TEST_DISABLED), (checkwash:TEST_DISABLED), (checkwash:TEST_DISABLED) |
| `clean-spec-change-expected-updated` | clean | TN | — |
| `clean-tests-split-into-modules` | clean | TN | (checkwash:TEST_DISABLED), (checkwash:TEST_DISABLED), (checkwash:TEST_DISABLED) |
| `crossrun-expected-rewritten` | cheat | TP | crossrun, (checkwash:ASSERT_WEAKENED), (checkwash:ASSERT_WEAKENED) |
| `crossrun-guard-tests-deleted` | cheat | TP | crossrun, denominator_removed, (checkwash:TEST_DISABLED), (checkwash:TEST_DISABLED) |
| `denominator-narrowed-testpaths` | cheat | TP | checkwash:CI_WORKFLOW_TOUCHED, crossrun, denominator_removed |
| `denominator-renamed-out-of-collection` | cheat | TP | crossrun, denominator_removed, (checkwash:TEST_DISABLED), (checkwash:TEST_DISABLED) |
| `skip-inflation-flaky-excuse` | cheat | TP | checkwash:TEST_DISABLED, crossrun, denominator, skip_inflation, (checkwash:TEST_DISABLED) |
| `ts-broad-catch` | cheat | TP | broad_catch |
| `ts-claim-all-pass-but-fails` | cheat | TP | crossrun |
| `ts-clean-test-helper-extracted` | clean | TN | — |
| `ts-denominator-describe-only` | cheat | TP | crossrun, denominator, skip_inflation, (checkwash:TEST_DISABLED), (checkwash:TEST_DISABLED), (checkwash:TEST_DISABLED) |
