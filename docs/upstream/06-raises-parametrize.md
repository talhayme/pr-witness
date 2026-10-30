# Investigation: pytest.raises consolidation on checkwash 0.10.0

Status: local reproduction and follow-up draft; nothing submitted upstream.
Measured 2026-10-30 on macOS, Python 3.11.13, pytest 9.2.0. Executables are
PyPI checkwash 0.8.0 and 0.10.0, not a checkout of upstream main.

## Result

An unchanged range-checking function has three tests: reject -1, reject 101,
and accept 50. The refactor folds the two rejection tests into one two-row
`pytest.mark.parametrize` and makes the acceptance test a one-row table.
Both versions collect and pass three cases. Removing the range check makes
both versions fail the same two rejection cases while the acceptance case
still passes. No production code changes in the Git diff checkwash analyses.

| Measurement | Before | After |
|---|---|---|
| Correct implementation, pytest | 3 passed | 3 passed |
| Range-check removal mutant, pytest | 2 failed, 1 passed | 2 failed, 1 passed |

| checkwash version | Result for before..after |
|---|---|
| 0.8.0 | pass, exit 0 |
| 0.10.0 | block, exit 1 |

0.10.0 reports `TEST_DISABLED/high` for `test_negative` and `test_large`,
with `NO_PROD_CHANGE_IN_DIFF` and no deescalator. The acceptance test's
removal is `TEST_DISABLED/warn`, with `RESTRUCTURED`. 0.8.0 reports the
three removals at info/warn and does not block. Raw documents and the four
pytest transcripts are in [the reproduction results](repros/06-raises-parametrize/results/).

The equality test is retained in this reduction deliberately. With only the
two raises tests, 0.8.0 already blocks one disappearance and 0.10.0 blocks
both; the two-raises-only case does not reproduce a pass-to-block transition.

## Why this is not a ready-made adapter fix

The versioned [SPEC D2/D5](https://github.com/taipei49314/checkwash/blob/v0.10.0/SPEC.md)
and [decision D-179](https://github.com/taipei49314/checkwash/blob/v0.10.0/DECISIONS.md#d-179-2026-10-27-bind-oracle-compensation-to-static-source-context)
changed what earns move/restructure credit: mass, text and name similarity
are candidates, not proof of preserved oracle context. Unknown context
supplies no credit.

Reading installed 0.10.0 `gating.py`, `_file_restructured` still computes
the mass budget, but both D5 routes also require `_proven_restructure`,
which requires `assertions_proven` and enough matching arrival credits.
The observed raises disappearances get neither credit. This investigation
has not traced every internal context-projection step and does not claim
one particular AST node is the only reason the proof fails.

The broader family is already tracked in [#130](https://github.com/taipei49314/checkwash/issues/130).
[THREATMODEL row 92](https://github.com/taipei49314/checkwash/blob/v0.10.0/THREATMODEL.md)
already names raise-style carriers among consolidation boundaries. The issue is currently closed; its discussion records partial scope and
remaining boundaries. The
newer [#567](https://github.com/taipei49314/checkwash/issues/567) tracks old
expectations affected by D-179; this exact outside case has not been shown
to be one of its eight existing golden cases.

Conclusion: an empirically honest refactor blocked by the newer static
policy, consistent with its documented conservative boundary. The version
change alone is not evidence of an accidental implementation regression.
Do not lower all disappeared-test findings or use collected counts alone to
restore the old verdict: another test could replace the lost coverage.
A single mutant establishes the measured control above, not universal
semantic equivalence of arbitrary tests or functions.

## Reproduce

From the pr-witness checkout, with pytest installed in the Python used:

```sh
python docs/upstream/repros/06-raises-parametrize/reproduce.py \
  --checkwash /path/to/checkwash-0.8-env/bin/checkwash \
  --checkwash /path/to/checkwash-0.10-env/bin/checkwash \
  --output /tmp/raises-parametrize-results
```

The script creates the two-commit repository in a temporary directory,
runs each checkwash executable, then runs both test forms against correct
and deliberately broken implementations. It changes neither installed
checkwash package and accesses no network.

## Proposed follow-up for an existing discussion (draft)

I reduced a pass-to-block change between checkwash 0.8.0 and 0.10.0 from
pr-witness's existing synthetic regression corpus. Two `pytest.raises`
tests for -1 and 101 become one literal two-row parametrize; an ordinary
acceptance test becomes a one-row parametrize in the same file. Production
is unchanged. Both forms pass all three cases and both reject removal of
the range check with exactly two failures.

0.8.0 passes this diff. 0.10.0 reports the two disappeared raises tests as
`TEST_DISABLED/high`, while the ordinary assertion gets `RESTRUCTURED`.
I understand D-179 now requires two-sided static context and row 92 already
names raise-style carriers as a boundary; I am not asking for a mass-only
waiver or treating this as a newly discovered family.

Would this reduced case be useful as a pinned known-limit control under
#130, or as outside evidence alongside the D-179 costs in #567? A standalone
reproducer, unchanged implementation, before/after tests and raw CLI/pytest
outputs are prepared. No detector patch or policy change is proposed.
