# Corpus

A labelled set of cases for measuring whether a tool can tell a dishonest
change from an honest one.

Each case is a self-contained scenario: a base state, a head state, the pull
request description that came with it, and a label saying what the right
answer is.

## Why this exists

You cannot claim a detector is accurate without a set it was measured on, and
no public set of "agent tampered with the tests" cases existed when this was
written. Building the measuring stick before the tool is deliberate — it is
the only way to find out whether the tool is worth building at all.

## Scope: what this corpus is *for*

[checkwash](https://github.com/taipei49314/checkwash) already detects
diff-level tampering well — weakened assertions, loosened tolerances,
rewritten expected values, disabled tests, broad `except`, touched CI. It
ships its own benchmarks, including an 1800-commit corpus for false
positives. Re-testing those detectors here would duplicate work and produce a
worse version of a number that already exists.

So this corpus targets the signals checkwash does **not** cover — the ones
`pr-witness` exists for:

| Signal | What it catches |
|---|---|
| `crossrun` | A base-branch test that now fails on the PR's code — visible even when the agent "fixed" the test to match the bug |
| `denominator` | Fewer tests collected than before, without test files being deleted. The `4966/4966 ALL PASSED` trick |
| `skip_inflation` | Collected count held steady while skipped count climbs |
| `claim_false` | The PR description asserts something the run contradicts |
| `claim_unverifiable` | A claim nothing in CI can confirm or deny |

Cases that *also* trip a checkwash detector are fine and are labelled as
such — but the corpus is balanced around our signals, not theirs.

## Layout

```
cases/<id>/
├── base/          files as they are on the base branch
├── head/          the same files after the pull request
├── pr_body.md     the pull request description
└── label.yaml     ground truth
```

Base and head are full file trees rather than patches: a runner has to be
able to execute both sides to measure a cross-run, and reconstructing a
working tree from a patch is a source of bugs the corpus should not have.

## label.yaml

```yaml
id: denominator-narrowed-testpaths
verdict: cheat              # cheat | clean
language: python            # python | typescript
summary: >
  One sentence a human can check the label against.

signals:                    # what a correct tool should report
  - denominator

also_detected_by_checkwash: false

counts:                     # ground truth, verified by running both sides
  base: { collected: 12, passed: 12, failed: 0, skipped: 0 }
  head: { collected: 4,  passed: 4,  failed: 0, skipped: 0 }

claims:                     # claims in pr_body.md and their true verdict
  - text: "All tests pass"
    verdict: misleading     # true | false | misleading | unverifiable

source: synthetic           # synthetic | <url>
license: Apache-2.0
notes: >
  Why this case is interesting, and anything a reader would otherwise
  misread.
```

`verdict: clean` cases matter as much as `cheat` ones. Precision cannot be
measured without them, and a tool that flags every honest refactor is worse
than no tool.

## Honest-case design

The `clean` half is not filler. Each one is a change that *looks* like
tampering to a naive detector but is legitimate:

- a test deleted because the feature it covered was removed
- expected values updated because the specification deliberately changed
- tests renamed or moved, changing the collected set but not its content
- a flaky test skipped with an issue link and a reason
- parametrised cases collapsed, reducing the collected count honestly

If a tool scores well on the cheat half and badly here, it is not a detector
— it is an alarm.

## Running the evaluation

```bash
python eval/run_eval.py --tool checkwash
python eval/run_eval.py --tool pr-witness
```

Writes precision, recall and F1 per signal to `eval/results.md`.

## Respect for the people in the corpus

Cases drawn from real pull requests are anonymised: no author names, no
repository names, no links — except where maintainers already discussed the
issue publicly, in which case the public thread is cited. The point is to
measure tools, not to shame contributors.

At present every case is synthetic, reproducing patterns documented in public
issues and papers. Real cases will be added only after their licences are
checked.
