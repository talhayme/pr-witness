[missed cheat] JS/TS: `eslint-disable` of a rule that enforces that tests assert something passes with zero findings

## The cheat

Several lint rules are verification-layer rules. Disabling one in a test file
is materially the same act as weakening an assertion, and it is a one-line
diff at the top of the file that reads as housekeeping.

Checked against checkwash 0.6.0.

## Reproduction

`cart.ts` unchanged; one line added to the test file.

**before**

```ts
// cart.test.ts
import { describe, expect, it } from "vitest";
import { withTax } from "./cart";

describe("withTax", () => {
  it("rounds", () => {
    expect(withTax(10.005, 0.1)).toBe(11.01);
  });
});
```

**after**

```ts
/* eslint-disable vitest/expect-expect, vitest/no-disabled-tests */
import { describe, expect, it } from "vitest";
// ... unchanged
```

**result**

```
$ checkwash check BASE..HEAD --format json
verdict: pass | findings: 0
```

With those two rules off, a later commit can land a test with no assertion at
all, or a `.skip`, and the linter will not say so.

## Which rules, and which not

The signal is narrow on purpose. Disabling `@typescript-eslint/no-unused-vars`
in a test is housekeeping and must not be reported. The rules that matter are
the ones asserting that a test tests something:

| Rule | What disabling it allows |
|---|---|
| `jest/expect-expect`, `vitest/expect-expect` | a test with no assertion at all |
| `jest/no-disabled-tests`, `vitest/no-disabled-tests` | skipped tests stop being flagged |
| `jest/no-focused-tests`, `vitest/no-focused-tests` | `.only` narrowing the run |
| `jest/no-conditional-expect`, `vitest/…` | an assertion behind an `if` that may never run |
| `jest/no-commented-out-tests`, `vitest/…` | a test commented out rather than deleted |
| `jest/valid-expect`, `vitest/valid-expect` | a malformed `expect` that never executes |

One more case worth handling: a bare `/* eslint-disable */` names no rules,
which means all of them, including every rule above.

Keeping the list small and explicit matters more than covering every plugin.
A detector that fires on `eslint-disable-next-line prettier/prettier` would be
turned off within a week.

## Context

Found while building a labelled corpus for a tool that runs the base branch's
tests against a PR's code; checkwash is a dependency of it rather than a
competitor. Of the three gaps I found, this is the one I am least sure belongs
upstream — it is arguably a lint-config concern rather than a diff-integrity
one. Filing it so the decision is yours rather than mine by omission.
