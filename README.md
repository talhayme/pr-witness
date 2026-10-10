# pr-witness

Checks whether a pull request's tests still mean what they meant before it.

A test suite is a claim: *these behaviours hold*. A change can keep the suite
green while quietly withdrawing the claim — by narrowing what gets collected,
by rewriting the expected value to match a new bug, by skipping the test that
guarded the thing it broke. CI reports green either way, because CI only ever
runs the new tests against the new code.

pr-witness runs the combination nobody runs: **the base branch's tests against
the pull request's code.** A test that passed before and fails now is a
regression the pull request hid, whatever the green checkmark says.

## Status

Phase 0 complete: a labelled corpus and a measured baseline. The tool itself
is not built yet — the measuring stick came first, deliberately, because it is
the only way to find out whether the tool is worth building.

See [eval/results.md](eval/results.md) for the numbers and
[corpus/README.md](corpus/README.md) for how the cases are built.

## The signals

| Signal | What it catches |
|---|---|
| `crossrun` | A base-branch test that now fails on the PR's code |
| `denominator` | Fewer tests actually running than before — the `4966/4966 ALL PASSED` trick |
| `skip_inflation` | Collected count steady while the skipped count climbs |
| `claim_false` | The description asserts something the run contradicts |
| `claim_unverifiable` | A claim nothing in CI can confirm or deny |

## Relationship to checkwash

[checkwash](https://github.com/taipei49314/checkwash) detects diff-level
tampering — weakened assertions, loosened tolerances, disabled tests, touched
CI — and does it well, with its own published benchmarks. pr-witness is not a
replacement and does not re-test those detectors. It covers what a diff cannot
show: what happened when the code actually ran.

Run both.

## Reproducing the baseline

```bash
python -m venv venv && ./venv/bin/pip install checkwash pytest
(cd .tsrunner && npm install)

python corpus/build.py         # generate the 16 cases
python corpus/verify.py        # measure the Python cases
python corpus/verify_ts.py     # measure the TypeScript cases
python eval/run_eval.py --tool checkwash
python eval/run_eval.py --tool crossrun
```

## Licence

Apache-2.0.
