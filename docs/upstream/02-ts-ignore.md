[missed cheat] JS/TS: `@ts-nocheck` added to a test file passes with zero findings, removing type checking from every test in it

## The cheat

One line at the top of a test file turns off type checking for everything
below it. The type checker is part of what stops a test from silently going
stale: without it, a test keeps compiling after the thing it tests changes
shape — which is the moment it should have failed and told someone.

Checked against checkwash 0.6.0.

## Reproduction

`cart.ts` unchanged; one line added to the test file.

**before**

```ts
// cart.test.ts
import { expect, it } from "vitest";
import { withTax } from "./cart";

it("rejects a bad amount", () => {
  expect(() => withTax(-1, 0.1)).toThrow();
});
```

**after**

```ts
// @ts-nocheck
import { expect, it } from "vitest";
import { withTax } from "./cart";

it("rejects a bad amount", () => {
  expect(() => withTax(-1, 0.1)).toThrow();
});
```

**result**

```
$ checkwash check BASE..HEAD --format json
verdict: pass | findings: 0
```

## Severity, and where I would not report it

`@ts-ignore` on a single line is genuinely common and often legitimate — a
third-party type bug, or a test that deliberately passes an invalid value to
check it is rejected. Reporting every one would be noise.

`@ts-nocheck` on a test file is different in kind: it is never narrow, and
there is no single line it is defending. A graded shape that seems defensible:

- `@ts-nocheck` added to a test file — the clear case
- `@ts-ignore` / `@ts-expect-error` added on, or immediately above, a line
  containing an assertion — arguable, lower severity
- anywhere else in the file — not reported

This one is more of a policy question than #1 (the `try`/`catch` parity gap),
and "we would rather not carry this" is a perfectly good answer. I am
carrying it locally either way; I would just rather know which side the line
falls on.

## Unrelated, noticed in the same run

Both revisions emit:

```
checkwash: analysis incomplete: before cart.test.ts:5:3: expect(...).toThrow:
expect assertion candidate is recorded with no strength: its predicate is not
represented in the assertion scan, so a rewrite is not judged
```

So `toThrow` appears to carry no strength and a rewrite of it would not be
judged. Not what this issue is about, and I have not tested it properly —
mentioning it only so it is not buried. Happy to open it separately if it is
news.
