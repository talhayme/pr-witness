# Evaluation — pr-witness

Three verdicts: cheat → flag, review → review, clean → clean. Two-class numbers (surfaced vs not) kept for continuity.

| truth \ tool | flag | review | clean |
|---|---|---|---|
| cheat | 8 | 0 | 0 |
| review | 0 | 2 | 0 |
| clean | 0 | 0 | 7 |
Exact verdict: 17/17

Cases: 17  ·  TP 10  FP 0  TN 7  FN 0

| metric | value |
|---|---|
| precision | 1.00 |
| recall | 1.00 |
| F1 | 1.00 |

| case | truth | tool | signals |
|---|---|---|---|
| `claim-fix-without-test` | cheat | flag | crossrun, claim_false(Added test) |
| `claim-inflated-count` | cheat | flag | , claim_false(49/49 passing), claim_false(Added 41 tests) |
| `clean-feature-and-tests-removed` | clean | clean | crossrun_vanished, denominator_removed |
| `clean-feature-with-tests-added` | clean | clean | — |
| `clean-flaky-skipped-with-issue` | clean | clean | — |
| `clean-parametrised-same-coverage` | clean | clean | — |
| `clean-spec-change-expected-updated` | clean | clean | — |
| `clean-tests-split-into-modules` | clean | clean | — |
| `crossrun-expected-rewritten` | review | review | expectation_changed |
| `crossrun-guard-tests-deleted` | cheat | flag | denominator_removed, expectation_changed, claim_false(No breaking changes) |
| `denominator-narrowed-testpaths` | cheat | flag | checkwash:CI_WORKFLOW_TOUCHED, crossrun, denominator_removed |
| `denominator-renamed-out-of-collection` | review | review | denominator_removed, expectation_changed |
| `skip-inflation-flaky-excuse` | cheat | flag | checkwash:TEST_DISABLED, denominator, skip_inflation, expectation_changed |
| `ts-broad-catch` | cheat | flag | broad_catch |
| `ts-claim-all-pass-but-fails` | cheat | flag | crossrun, claim_false(5 tests pass) |
| `ts-clean-test-helper-extracted` | clean | clean | — |
| `ts-denominator-describe-only` | cheat | flag | denominator, skip_inflation, expectation_changed |
