# Proposals for checkwash

The plan pr-witness follows says: detectors that belong in checkwash should
be offered to checkwash first, and kept here only if the maintainer declines.
This directory holds those proposals and their status.

## Status

| # | Topic | Status |
|---|---|---|
| [01](01-broad-catch-js.md) | `try`/`catch` swallowing an assertion | **fixed in checkwash v0.7.0** (12 Oct 2026) as `BROAD_EXCEPT_ADDED`; [checkwash#363](https://github.com/taipei49314/checkwash/issues/363) closed 14 Oct, credited in their fixtures and `benchmarks/FAILURES.md`. pr-witness's own check now steps aside where checkwash reports it. |
| [02](02-ts-ignore.md) | `@ts-nocheck` on a test file | [checkwash#366](https://github.com/taipei49314/checkwash/issues/366): confirmed, deferred from v0.7.0 (14 Oct) |
| [03](03-eslint-disable.md) | `eslint-disable` of a test-quality rule | [checkwash#367](https://github.com/taipei49314/checkwash/issues/367): confirmed, deferred from v0.7.0; open whether it is lint configuration rather than diff integrity (14 Oct) |
| — | Proposal: shared corpus + findings contract | [checkwash#364](https://github.com/taipei49314/checkwash/issues/364): answered 14 Oct — cases welcome one per issue via their templates; the contract is `docs/stability.md` (pin exactly in CI); and a correction we have taken: checkwash does not block every added skip, and does not read skip reasons by design. |

All four were filed on 10 October 2026, on the repository owner's
instruction. The original plan was to send 01 first and hold 02 and 03
until it was answered; in hindsight that plan was the better one — four
issues in one day is a lot to put in front of a single maintainer, however
well each is argued — and no further reports went to checkwash until one
had a reply. All four were answered on 14 October; new cases now go one per
issue, as the maintainer asked.

Nothing is filed without the repository owner's approval. The reports were
researched and drafted with Claude Code and checked by the owner before
sending; every measurement in them is reproducible from this repository.

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

## SWE-chat

A note to the dataset's authors — what was built on it and two observations about
`commits.parquet` (row-group size, `is_agent_author`) — filed as
[SALT-NLP/SWE-chat#2](https://github.com/SALT-NLP/SWE-chat/issues/2) on 2026-10-11.
