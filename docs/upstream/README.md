# Proposals for checkwash

The plan pr-witness follows says: detectors that belong in checkwash should
be offered to checkwash first, and kept here only if the maintainer declines.
This directory holds those proposals and their status.

**Nothing here has been sent yet.** Each file is a draft issue awaiting the
repository owner's approval before it is filed.

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
