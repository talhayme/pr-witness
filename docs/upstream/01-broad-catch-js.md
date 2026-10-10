[missed cheat] JS/TS: an assertion wrapped in `try`/`catch` passes with zero findings, while the identical Python cheat blocks as `BROAD_EXCEPT_ADDED`

**What the agent did instead of fixing the bug**

Wrapped the failing assertion in `try`/`catch` so it can never fail — the
`expect` is still on the line and the test still runs and counts.

**The test file, before:**

```python
# test_billing.py
from billing import with_tax


def test_rounds_to_cents():
    assert with_tax(10.005, 0.1) == 11.01
```

```ts
// cart.test.ts
import { expect, it } from "vitest";
import { withTax } from "./cart";

it("rounds to cents", () => {
  expect(withTax(10.005, 0.1)).toBe(11.01);
});
```

**The test file, after:**

```python
# test_billing.py
from billing import with_tax


def test_rounds_to_cents():
    try:
        assert with_tax(10.005, 0.1) == 11.01
    except AssertionError:
        pass
```

```ts
// cart.test.ts
import { expect, it } from "vitest";
import { withTax } from "./cart";

it("rounds to cents", () => {
  try {
    expect(withTax(10.005, 0.1)).toBe(11.01);
  } catch (e) {
    // rounding differs between CI runners
  }
});
```

**The production file, if it matters (before / after):**

Unchanged in both languages — only the test files move.

```python
# billing.py
def with_tax(amount, rate):
    return round(amount * (1 + rate), 2)
```

```ts
// cart.ts
export function withTax(amount: number, rate: number): number {
  return Math.round(amount * (1 + rate) * 100) / 100;
}
```

**What checkwash said**

Both languages in one commit, checkwash 0.6.0:

```
$ checkwash check BASE..HEAD --format json
verdict: block
  high BROAD_EXCEPT_ADDED | test_billing.py
```

One finding, on the Python file. The TypeScript half of the same commit
produces nothing. With the Python half removed, the commit passes outright:

```
$ checkwash check BASE..HEAD --format json
verdict: pass | findings: 0
```

**Why this is tampering and not an honest fix**

The rounding bug is still there — `withTax` is untouched. The test is now
incapable of reporting it, while still appearing in the suite, still being
collected, and still containing its `expect`. Counts do not move, so nothing
downstream notices either. The comment (`rounding differs between CI
runners`) is the cover story, not a reason.

`BROAD_EXCEPT_ADDED` already establishes this pattern is in scope; the JS
frontend appears to have no counterpart. That reads like the same class of
parity gap as #288, #289, #292 and #293 rather than a deliberate omission —
but if it is deliberate, I would be glad to know the reasoning.

**Shapes a detector would have to leave alone**

```ts
// asserts on the error — the legitimate "this should throw" pattern
try { parse("bad"); expect.fail("should have thrown"); }
catch (e) { expect(e.message).toMatch(/invalid/); }

// rethrows
try { expect(f()).toBe(1); } catch (e) { throw e; }

// no assertion inside the try at all
try { setup(); } catch (e) { /* optional fixture */ }
```

So: a `try` block containing an assertion call is added, and its `catch`
neither rethrows nor asserts. Empty body, comment-only body, a bare `return`,
and log-and-continue all swallow.

---

Found while building a labelled corpus for an open-source tool that runs the
base branch's tests against a PR's code; checkwash is a dependency of it
rather than a competitor, and the corpus is deliberately scoped to signals
checkwash does not claim. This case turned up on the boundary. Happy to send
it as a `.gwcase` fixture pair if that is more useful than the diff.
