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

Phases 0–6 complete: corpus, cross-run, diff integrity (via checkwash),
claim checking, the GitHub Action, signed evidence and the Claude Code plugin.
On PyPI (`pip install pr-witness`), on the GitHub Marketplace, and installable
as a Claude Code plugin.

**On the numbers.** The evaluation corpus is 17 *synthetic* cases, written by
the same person who wrote the detector, scored on three verdicts: a cheat must
be flagged, a rewritten expectation must come back as `review`, a clean change
must be left alone. The tool gets all 17 right —
[eval/witness_results.md](eval/witness_results.md). That is a regression gate,
not an accuracy claim: it says the tool has not got worse, not how it performs
on pull requests it has never seen.

The first **real** cases are in the loop: [corpus/real/swebench](corpus/real/swebench/)
holds seven test edits made by a frontier agent on SWE-bench Verified, out of
1,500 published patches examined, labelled against the maintainers' own test
patches. Six run end to end today (SymPy ×3, Sphinx, Django ×2); the tool's
verdict matches the label on all six — one `clean`, five `review`, each
`review` showing the old and the new assertion side by side. Before the
`review` verdict existed, three of the first four honest specification
changes came back as a flag; that run is what produced the verdict. The
Matplotlib case waits on a source build.

See [eval/results.md](eval/results.md) for the numbers and
[corpus/README.md](corpus/README.md) for how the cases are built.

## The signals

| Signal | What it catches |
|---|---|
| `crossrun` | A base-branch test the PR did **not** touch that now fails on the PR's code — a hidden regression (high) |
| `expectation_changed` | A test the PR **rewrote** whose old assertion fails on the new code; the report shows the old and new assertion (medium → `review`) |
| `denominator` | Fewer tests actually running than before — the `4966/4966 ALL PASSED` trick |
| `skip_inflation` | Collected count steady while the skipped count climbs |
| `claim_false` | The description asserts something the run contradicts |
| `claim_unverifiable` | A claim nothing in CI can confirm or deny |

## As a GitHub Action

```yaml
# .github/workflows/pr-witness.yml
name: pr-witness
on: pull_request
permissions:
  contents: read
  pull-requests: write      # for the comment

jobs:
  witness:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v7
        with: { fetch-depth: 0 }     # both branches must be present
      - uses: actions/setup-python@v7
        with: { python-version: "3.12" }
      - run: pip install -e . pytest  # whatever your own test job installs
      - uses: talhayme/pr-witness@v0.1
        with:
          test-command: pytest        # or vitest, jest, go, django (Django's own runtests.py)
          mode: report                # report | require-ack | strict
```

It posts one comment per pull request and edits it on every push, so the
thread does not fill with stale reports. The same report goes to the job
summary, and `evidence.json` is exposed as an output for anything downstream.

| mode | behaviour |
|---|---|
| `report` | never fails the job. The default. |
| `require-ack` | fails on a flag until a maintainer adds the `test-change-approved` label |
| `strict` | fails on a flag; the label documents intent but does not change the facts |

A *flag* is a disproved claim or a high finding. A *review* is a rewritten
test whose old assertion fails on the new code: honest specification change
or test bent to fit a bug, the run cannot tell, so it shows both assertions
and `require-ack`/`strict` hold the job for a human the same way they do for
a flag. Other medium findings and misleading claims are reported but never
fail the job in any mode.

Locally, the same thing:

```bash
pip install pr-witness
pr-witness --base origin/main                   # text report
pr-witness --base origin/main --format markdown --pr-body pr.md
pr-witness --base origin/main --mode require-ack --approved
pr-witness --base origin/main --changed-only      # only the test files the change touches
pr-witness --base origin/main --paths tests/api   # or a subset you name; large suites in seconds
```

### Signed evidence

With `sign: "true"` (the default) the action signs `evidence.json` with
[GitHub Artifact Attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations),
and the comment links to the attestation. That is what makes the report
worth more than a comment an agent could have typed: it proves the file was
produced by this workflow, in CI, and not altered since.

```bash
gh attestation verify evidence.json --repo you/your-repo \
  --predicate-type https://github.com/talhayme/pr-witness/evidence/v1
```

The job needs `id-token: write`, `attestations: write` and
`artifact-metadata: write`. **Signing works in public repositories on every
GitHub plan; private repositories need Enterprise Cloud.** When it cannot run
the report is still posted, marked "Unsigned" with the reason.

The evidence format is [`schema/evidence.v1.json`](schema/evidence.v1.json).

### How to clear a false alarm

1. Read the finding's "↳" line — every one says when it is innocent.
2. If the behaviour change is intentional, say so in the pull request and
   add `test-change-approved`. In `require-ack` mode that is enough.
3. If pr-witness is wrong, [open an issue](../../issues) with the diff; it
   becomes a `clean` case in the corpus so the next release cannot regress.

## In Claude Code

```bash
claude plugin marketplace add talhayme/pr-witness
claude plugin install pr-witness
```

Three small things, all advisory:

- **A pause before a test file changes.** Editing, writing or `rm`/`mv`/`sed`-ing
  a test file asks for confirmation, with the reasoning: *"if the behaviour is
  meant to change, say so; if the test is in the way, fix the code — CI will
  run the old test against the new code either way."* `PR_WITNESS_GUARD=deny`
  for a hard no, `PR_WITNESS_GUARD=off` to silence it.
- **A check when the agent says the tests pass.** When the final message makes
  a checkable claim — "all tests pass", "12/12 green", "added tests for X" —
  the hook runs `pr-witness` on the working tree against the base branch and
  shows any claim the run contradicts, in the session. It never blocks the
  stop: a hook that refused to let the agent finish until the numbers matched
  would teach it to stop giving numbers.
- **`/pr-witness:verify-before-done`** — a checklist: run the whole suite,
  quote the runner's own summary line, report the denominator, list every
  changed test with its reason.

The plugin is a courtesy, not a control. The agent runs inside its own
environment and can route around any hook. The proof is the signed report
from CI, where the agent cannot reach.

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

<!-- first live run of the action: see the pull request this line arrived in -->
