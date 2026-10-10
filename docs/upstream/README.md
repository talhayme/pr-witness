# Proposals for checkwash

The plan pr-witness follows says: detectors that belong in checkwash should
be offered to checkwash first, and kept here only if the maintainer declines.
This directory holds those proposals and their status.

## Status

| # | Topic | Status |
|---|---|---|
| [01](01-broad-catch-js.md) | `try`/`catch` swallowing an assertion | **filed: [checkwash#363](https://github.com/taipei49314/checkwash/issues/363)** (10 Oct 2026) |
| [02](02-ts-ignore.md) | `@ts-nocheck` on a test file | draft, held |
| [03](03-eslint-disable.md) | `eslint-disable` of a test-quality rule | draft, held |
| — | Proposal: shared corpus + findings contract | **filed: [checkwash#364](https://github.com/taipei49314/checkwash/issues/364)** (10 Oct 2026) |

02 and 03 are deliberately held back. 01 is the strongest of the three — a
clear parity gap, reproducible in one command — and makes a better first
contact than three at once. If it lands well, the others follow; if the
answer is "out of scope", three simultaneous declines would have been worse
than one.

Nothing is filed without the repository owner's approval.

Target: https://github.com/taipei49314/checkwash (Apache-2.0, active —
25 open issues, last push 10 Oct 2026).

Its CONTRIBUTING asks for exactly this: *"The most valuable thing you can
send is a cheat checkwash missed... You do not need to write any code to do
it."* Reports are reviewed quarterly and credited in `benchmarks/FAILURES.md`.
The drafts follow its house format — a `[missed cheat]` title, a before/after
that reproduces, and the actual command output.

Checked for duplicates against all 60 issues (open and closed) on
10 Oct 2026: none of the three is already filed. Parity between the Python
and JavaScript frontends is a recurring theme there (#288, #289, #292, #293),
which is the same class as draft 01.

## What was actually measured

The plan was written against checkwash v0.5 and assumed JS/TS support was
weak. Against **0.6.0** that is mostly no longer true. Probing each item on
the plan's list:

| Pattern (JS/TS) | checkwash 0.6.0 |
|---|---|
| `expect(...)` removed | ✅ `ASSERT_REMOVED` |
| `.skip` / `xit` / `xdescribe` added | ✅ `TEST_DISABLED` |
| `.only` narrowing the run | ✅ `TEST_DISABLED` |
| `toBeCloseTo` with reduced precision | ✅ `ASSERT_WEAKENED` |
| `expect.anything()` instead of a value | ✅ `ASSERT_WEAKENED` |
| `vi.mock`/`jest.mock` on the module under test | ✅ `TEST_PATCHES_SUBJECT` |
| CI `continue-on-error`, `\|\| true` | ✅ `CI_WORKFLOW_TOUCHED` |
| **`try`/`catch` swallowing an assertion** | ❌ gap — see [01](01-broad-catch-js.md) |
| **`// @ts-ignore` added on an asserting line** | ❌ gap — see [02](02-ts-ignore.md) |
| **`eslint-disable` added in a test** | ❌ gap — see [03](03-eslint-disable.md) |

So seven of the ten items the plan listed as missing are already done. Three
remain, and all three are the same shape: a suppression that makes a check
stop checking without removing it.

The first is a clear parity gap — `BROAD_EXCEPT_ADDED` exists and fires on
the Python equivalent, but has no JavaScript counterpart.
