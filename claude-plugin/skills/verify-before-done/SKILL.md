---
name: verify-before-done
description: Use before saying a task is done, finished, complete, or that tests pass. Runs the whole suite, reports the real numbers, lists every test that was changed and why, and refuses to shrink the denominator. Also use when asked to "double-check", "make sure it's green", or before opening a pull request.
---

# Verify before "done"

"Done" is a claim. This skill makes it a claim with evidence.

## Run everything, not the part you touched

Run the **full** suite with the project's normal command, from a clean
state. Not `-k`, not a single file, not `--lf`. If the suite is slow, say
how long it took; do not narrow it.

Record the line the runner prints — `N passed, M failed, K skipped` — and
quote **that line**, not a paraphrase.

## Report the denominator

Say how many tests were **collected**, not only how many passed. "12
passed" means something different when 30 were collected than when 12
were. If the collected count went down since the base branch, explain
where each missing test went.

## List every test you changed

For each test file touched: the test name, what changed, and **why** — one
of:

- the behaviour was meant to change, and the test now describes the new one
- the test was wrong about the old behaviour
- the test was removed because the feature was removed

"Flaky" is not a reason. A skip needs an issue number.

## Then write the summary

```
Tests: 30 collected, 30 passed, 0 failed, 0 skipped (pytest, 41s)
Changed tests:
  tests/test_dates.py::test_monday — behaviour change: Monday is now a
  business day per #318; expected value updated
Base-branch tests on this code: run `pr-witness --base origin/main`
```

If `pr-witness` is installed, run it and paste its claims section. If it
reports a disproved claim, the summary is wrong, not the tool.

## What not to do

- Do not edit a test to make it pass unless the behaviour is meant to change.
- Do not add `skip`, `.only`, `xfail`, `|| true`, or a `try/except` around
  an assertion to get to green.
- Do not say "all tests pass" after running a subset.
