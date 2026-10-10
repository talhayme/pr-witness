# `eslint-disable` added in a test file is not reported

**Status:** draft, not sent.

## What happens

```ts
/* eslint-disable jest/no-conditional-expect */
it("adds tax", () => { ... });
```
→ no findings against checkwash 0.6.0.

## Why it matters

Several lint rules *are* verification-layer rules. Disabling one of these in
a test is materially the same act as weakening an assertion:

| Rule | What disabling it allows |
|---|---|
| `jest/no-disabled-tests` | silently skipped tests stop being flagged |
| `jest/no-conditional-expect` | an assertion behind an `if` that may never run |
| `jest/expect-expect` | a test with no assertion at all |
| `jest/no-commented-out-tests` | a test commented out rather than deleted |
| `vitest/*` equivalents | the same, for vitest |

Disabling `no-unused-vars` in a test file is noise and should not be
reported. The signal is specifically about rules that enforce that tests
assert something.

## Suggested shape

Report only when the disabled rule is in a known verification-related set,
and only in files that the existing test-file classifier already identifies.
Severity medium: it is a real weakening, but a narrow and visible one.

Keeping the rule list small and explicit matters more than covering every
plugin — a detector that fires on `eslint-disable-next-line prettier/prettier`
would be ignored within a week.
