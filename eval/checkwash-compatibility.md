# checkwash adapter compatibility — 2026-10-30

Local validation on macOS, Python 3.11, with isolated environments for the
exact checkwash versions below. These are the existing regression cases,
not held-out evidence of precision or recall on real changes.

| checkwash | Unit tests | Existing end-to-end corpus |
|---|---|---|
| 0.8.0 | Final full suite: 189 passed; adapter/gate tests: 64 passed | 17/17 expected verdicts |
| 0.10.0 | Final full suite: 189 passed | 16/17 expected verdicts |

On 0.10.0, `clean-parametrised-same-coverage` gets two high `TEST_DISABLED`
findings and becomes `flag`. Repeating that case with the adapter from this
branch's starting commit produces the same findings and verdict. This is an
existing version-dependent result, not introduced by the adapter changes.
The corpus CI job remains pinned to 0.8.0; the unit-test matrix covers both
0.8.0 and 0.10.0. The package dependency range is unchanged.

Additional live 0.10.0 checks in temporary Git repositories:

- A reviewed exemption committed to the base side keeps `ASSERT_REMOVED`
  visible at informational severity in pr-witness.
- A changed 1,000,003-byte Python file makes checkwash exit 2 with
  `SourceOverLimit`; pr-witness reports the refusal and file path as an
  analysis note. The successful-response `unread` path is tested with a
  simulated version-2 response, not claimed as a live successful run.

Commands:

```sh
python -m pytest -q
python -m pytest tests/test_integrity.py tests/test_gate.py -q
python corpus/verify.py
python eval/run_witness.py
```

Generated corpus/report files were not replaced with these local runs.

The [reduced investigation](../docs/upstream/06-raises-parametrize.md) identifies
the D-179/static-context boundary and includes measured good/mutant controls.
The block is consistent with the documented conservative policy; it is not
classified here as an accidental adapter regression.
