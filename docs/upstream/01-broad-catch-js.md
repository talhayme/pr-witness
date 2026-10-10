# BROAD_EXCEPT_ADDED has no JavaScript counterpart

**Status:** draft, not sent.

## What happens

Wrapping an assertion in `try`/`catch` makes the test pass unconditionally
while leaving every `expect` in place. In Python, checkwash catches this:

```python
def test_adds_tax():
    try:
        assert with_tax(100, 0.2) == 120
    except AssertionError:
        pass
```
→ `BROAD_EXCEPT_ADDED` (high), verdict `block`.

The direct JavaScript translation is not caught:

```ts
it("adds tax", () => {
  try { expect(withTax(100, 0.2)).toBe(120); } catch (e) { /* flaky */ }
});
```
→ no findings, verdict `pass`.

Checked against checkwash 0.6.0.

## Why it matters

This is the cheapest way to neutralise a test while leaving it looking
intact: the assertion is still on the line, the test still runs, the diff
shows two added lines of error handling. A reviewer skimming the diff sees
defensive code, not a disabled check.

The Python detector establishes that this pattern is in scope. The gap is
one of language parity rather than of policy.

## Suggested shape

Fire when, inside a test unit, a `try` block is added that contains an
assertion call and whose `catch` neither rethrows nor asserts. Mirrors the
Python rule's existing logic:

- `catch` with an empty body, a comment only, or a bare `return`
- `catch` that logs and continues

Not fired when the `catch` asserts on the error, which is the legitimate
"this should throw" pattern and already common:

```ts
try { parse("bad"); expect.fail("should have thrown"); }
catch (e) { expect(e.message).toMatch(/invalid/); }
```

## Reproduction

A runnable pair of files is in
[`pr-witness/corpus/cases/ts-broad-catch/`](../../corpus/cases/ts-broad-catch).
