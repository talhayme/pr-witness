# `// @ts-ignore` added on an asserting line is not reported

**Status:** draft, not sent.

## What happens

```ts
it("adds tax", () => {
  // @ts-ignore
  expect(withTax("bad", 0.2)).toBe(120);
});
```
→ no findings against checkwash 0.6.0.

Also applies to `@ts-expect-error` and `@ts-nocheck` at the top of a test
file, which suppresses type checking for everything below it.

## Why it matters

The type checker is part of the verification layer. Silencing it on an
asserting line lets a test keep compiling after the thing it tests changed
shape — which is exactly the moment the test should have stopped compiling
and told someone.

`@ts-nocheck` is the strongest form: one line at the top of a file removes
type checking from every test in it.

## Why this one is arguable

Unlike the `try`/`catch` gap, this is a policy question rather than a parity
one. `@ts-ignore` is widely used for legitimate reasons — third-party type
bugs, a deliberate "this must reject invalid input" test.

A reasonable compromise, and what pr-witness implements locally:

- **high** only for `@ts-nocheck` in a test file, which is never narrow
- **medium** for a suppression added on or immediately above a line
  containing an assertion
- **not reported** elsewhere in the file

If checkwash would rather not carry this, that is an entirely defensible
answer and pr-witness will keep it.
