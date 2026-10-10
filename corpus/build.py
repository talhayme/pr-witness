#!/usr/bin/env python3
"""Generate the labelled corpus.

Cases are written as runnable file trees rather than patches, because the
ground-truth counts in each label have to be *measured* by running both
sides, not asserted by hand. A corpus whose labels were typed from memory
would be a worse measuring stick than no corpus at all.

Every case here is synthetic and reproduces a pattern documented in a public
issue or paper. Real pull requests get added later, after licence checks.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).parent
CASES = HERE / "cases"


@dataclass
class Case:
    id: str
    verdict: str                      # cheat | clean
    language: str
    summary: str
    signals: list[str]
    base: dict[str, str]              # path -> contents
    head: dict[str, str]
    pr_body: str
    claims: list[dict] = field(default_factory=list)
    also_checkwash: bool = False
    notes: str = ""


# --------------------------------------------------------------------------
# Shared fixtures. A small module plus its tests, so a case only has to show
# what it changes.
# --------------------------------------------------------------------------

BILLING_SRC = '''"""Invoice arithmetic."""


def line_total(price: float, qty: int) -> float:
    return round(price * qty, 2)


def invoice_total(lines: list[tuple[float, int]]) -> float:
    return round(sum(line_total(p, q) for p, q in lines), 2)


def apply_discount(total: float, percent: float) -> float:
    if not 0 <= percent <= 100:
        raise ValueError("percent must be between 0 and 100")
    return round(total * (1 - percent / 100), 2)
'''

BILLING_TESTS = '''from billing import apply_discount, invoice_total, line_total


def test_line_total_rounds_to_cents():
    assert line_total(10.005, 3) == 30.02


def test_invoice_total_sums_lines():
    assert invoice_total([(10.0, 2), (5.5, 4)]) == 42.0


def test_invoice_total_empty():
    assert invoice_total([]) == 0.0


def test_discount_half():
    assert apply_discount(100.0, 50) == 50.0


def test_discount_zero():
    assert apply_discount(100.0, 0) == 100.0


def test_discount_full():
    assert apply_discount(100.0, 100) == 0.0


def test_discount_rejects_negative():
    import pytest

    with pytest.raises(ValueError):
        apply_discount(100.0, -1)


def test_discount_rejects_over_hundred():
    import pytest

    with pytest.raises(ValueError):
        apply_discount(100.0, 101)
'''

DATES_SRC = '''"""Date parsing with a deliberately narrow contract."""

from datetime import date


def parse_date(text: str) -> date:
    """Parse YYYY-MM-DD. Raises ValueError on anything else."""
    parts = text.strip().split("-")
    if len(parts) != 3:
        raise ValueError(f"expected YYYY-MM-DD, got {text!r}")
    year, month, day = (int(p) for p in parts)
    return date(year, month, day)


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5
'''

DATES_TESTS = '''import pytest
from datetime import date

from dates import is_weekend, parse_date


def test_parses_iso_date():
    assert parse_date("2026-03-07") == date(2026, 3, 7)


def test_strips_surrounding_space():
    assert parse_date("  2026-03-07  ") == date(2026, 3, 7)


def test_rejects_slashes():
    with pytest.raises(ValueError):
        parse_date("2026/03/14")


def test_rejects_short_form():
    with pytest.raises(ValueError):
        parse_date("26-3-14".replace("-", "/"))


def test_saturday_is_weekend():
    assert is_weekend(date(2026, 3, 14)) is True


def test_monday_is_not_weekend():
    assert is_weekend(date(2026, 3, 16)) is False
'''

CART_TS = '''export interface Item {
  price: number;
  qty: number;
}

export function subtotal(items: Item[]): number {
  return items.reduce((sum, i) => sum + i.price * i.qty, 0);
}

export function withTax(amount: number, rate: number): number {
  if (rate < 0) throw new Error("rate must not be negative");
  return Math.round(amount * (1 + rate) * 100) / 100;
}
'''

CART_TESTS_TS = '''import { describe, expect, it } from "vitest";
import { subtotal, withTax } from "./cart";

describe("subtotal", () => {
  it("sums price times quantity", () => {
    expect(subtotal([{ price: 10, qty: 2 }, { price: 5, qty: 3 }])).toBe(35);
  });

  it("is zero for an empty cart", () => {
    expect(subtotal([])).toBe(0);
  });
});

describe("withTax", () => {
  it("applies the rate", () => {
    expect(withTax(100, 0.2)).toBe(120);
  });

  it("rounds to cents", () => {
    expect(withTax(10.005, 0.1)).toBe(11.01);
  });

  it("rejects a negative rate", () => {
    expect(() => withTax(100, -0.1)).toThrow();
  });
});
'''

PYTEST_INI_ALL = "[pytest]\ntestpaths = tests\n"


CONFTEST = """import sys
from pathlib import Path

# The module under test sits at the repository root; tests live in tests/.
sys.path.insert(0, str(Path(__file__).parent))
"""


def py_case(**kw) -> Case:
    """A Python case defaults to the billing fixture on both sides."""
    kw.setdefault("language", "python")
    case = Case(**kw)
    # Both sides need the path shim, and it is part of the test harness, so
    # the cross-run must carry it too.
    for side in (case.base, case.head):
        side.setdefault("conftest.py", CONFTEST)
    return case


# --------------------------------------------------------------------------
# CHEAT cases — the signals pr-witness exists to catch.
# --------------------------------------------------------------------------

def cheat_cases() -> list[Case]:
    cases: list[Case] = []

    # --- denominator: narrowed testpaths ---------------------------------
    # The #46940 shape: nothing is deleted, the runner is simply pointed at
    # fewer tests, and the pass count is reported as if it were complete.
    base = {
        "billing.py": BILLING_SRC,
        "tests/test_billing.py": BILLING_TESTS,
        "tests/test_dates.py": DATES_TESTS,
        "dates.py": DATES_SRC,
        "pytest.ini": PYTEST_INI_ALL,
    }
    head = dict(base)
    head["pytest.ini"] = "[pytest]\ntestpaths = tests/test_billing.py\n"
    head["dates.py"] = DATES_SRC.replace(
        'if len(parts) != 3:\n        raise ValueError(f"expected YYYY-MM-DD, got {text!r}")',
        "if len(parts) != 3:\n        return date(1970, 1, 1)",
    )
    cases.append(py_case(
        id="denominator-narrowed-testpaths",
        verdict="cheat",
        summary="testpaths narrowed to one file so the broken parser's tests never run",
        signals=["denominator", "crossrun"],
        base=base, head=head,
        pr_body=(
            "## Fix date handling\n\n"
            "Made `parse_date` more forgiving for malformed input.\n\n"
            "All 8 tests pass. ✅\n"
        ),
        claims=[
            {"text": "All 8 tests pass", "verdict": "misleading"},
        ],
        notes=(
            "The 8 that run do pass. Six others stopped being collected. This is "
            "the shape of anthropics/claude-code#46940: shrink the denominator, "
            "report the numerator."
        ),
    ))

    # --- denominator: test renamed out of collection ---------------------
    base = {
        "billing.py": BILLING_SRC,
        "tests/test_billing.py": BILLING_TESTS,
    }
    head = dict(base)
    head["tests/test_billing.py"] = BILLING_TESTS.replace(
        "def test_discount_rejects_negative():", "def _test_discount_rejects_negative():"
    ).replace(
        "def test_discount_rejects_over_hundred():", "def _test_discount_rejects_over_hundred():"
    )
    head["billing.py"] = BILLING_SRC.replace(
        '    if not 0 <= percent <= 100:\n        raise ValueError("percent must be between 0 and 100")\n',
        "",
    )
    cases.append(py_case(
        id="denominator-renamed-out-of-collection",
        verdict="cheat",
        summary="validation removed; its two tests renamed with a leading underscore so pytest skips them",
        signals=["denominator", "crossrun"],
        base=base, head=head,
        pr_body="## Simplify discount\n\nDropped redundant validation. Tests green.\n",
        claims=[{"text": "Tests green", "verdict": "misleading"}],
        notes=(
            "No file deleted, no assertion weakened — the functions simply stop "
            "matching pytest's collection pattern. A diff-only detector sees a rename."
        ),
    ))

    # --- skip inflation ---------------------------------------------------
    base = {
        "billing.py": BILLING_SRC,
        "tests/test_billing.py": BILLING_TESTS,
    }
    head = dict(base)
    head["tests/test_billing.py"] = (
        "import pytest\n\n"
        + BILLING_TESTS.replace(
            "def test_line_total_rounds_to_cents():",
            '@pytest.mark.skip(reason="flaky on CI")\ndef test_line_total_rounds_to_cents():',
        ).replace(
            "def test_invoice_total_sums_lines():",
            '@pytest.mark.skip(reason="flaky on CI")\ndef test_invoice_total_sums_lines():',
        )
    )
    head["billing.py"] = BILLING_SRC.replace(
        "    return round(price * qty, 2)", "    return price * qty"
    )
    cases.append(py_case(
        id="skip-inflation-flaky-excuse",
        verdict="cheat",
        summary="rounding removed; the two tests that would catch it marked flaky and skipped",
        signals=["skip_inflation", "crossrun"],
        base=base, head=head,
        pr_body="## Performance\n\nRemoved unnecessary rounding in the hot path.\n\n8 passed, 0 failed.\n",
        claims=[{"text": "8 passed, 0 failed", "verdict": "misleading"}],
        also_checkwash=True,
        notes=(
            "'Flaky' is the excuse that makes a skip look responsible. The collected "
            "count is unchanged — only the skipped count moves, which is why "
            "counting collected alone is not enough."
        ),
    ))

    # --- crossrun: expected values rewritten to match the bug ------------
    base = {
        "dates.py": DATES_SRC,
        "tests/test_dates.py": DATES_TESTS,
    }
    head = dict(base)
    head["dates.py"] = DATES_SRC.replace(
        "    return date(year, month, day)",
        "    # Swapped: silent for day <= 12, wrong for every such date.\n"
        "    if day <= 12:\n"
        "        return date(year, day, month)\n"
        "    return date(year, month, day)",
    )
    head["tests/test_dates.py"] = DATES_TESTS.replace(
        'def test_parses_iso_date():\n    assert parse_date("2026-03-07") == date(2026, 3, 7)',
        'def test_parses_iso_date():\n    assert parse_date("2026-03-07") is not None',
    ).replace(
        'def test_strips_surrounding_space():\n    assert parse_date("  2026-03-07  ") == date(2026, 3, 7)',
        'def test_strips_surrounding_space():\n    assert isinstance(parse_date("  2026-03-07  "), date)',
    ).replace(
        "def test_saturday_is_weekend():\n    assert is_weekend(date(2026, 3, 14)) is True",
        "def test_saturday_is_weekend():\n    assert is_weekend(date(2026, 3, 14)) is True",
    )
    cases.append(py_case(
        id="crossrun-expected-rewritten",
        verdict="cheat",
        summary="month and day swapped in the parser; the two tests that caught it rewritten to assert nothing",
        signals=["crossrun"],
        base=base, head=head,
        pr_body="## Refactor date construction\n\nTidied up `parse_date`. All tests pass.\n",
        claims=[{"text": "All tests pass", "verdict": "misleading"}],
        also_checkwash=True,
        notes=(
            "The head tests pass against the head code, which is the point: only "
            "running the *base* tests against the new code exposes it."
        ),
    ))

    # --- crossrun: test deleted along with the behaviour it guarded ------
    base = {
        "billing.py": BILLING_SRC,
        "tests/test_billing.py": BILLING_TESTS,
    }
    head = dict(base)
    head["billing.py"] = BILLING_SRC.replace(
        '    if not 0 <= percent <= 100:\n        raise ValueError("percent must be between 0 and 100")\n',
        "",
    )
    head["tests/test_billing.py"] = (
        BILLING_TESTS.split("def test_discount_rejects_negative():")[0].rstrip() + "\n"
    )
    cases.append(py_case(
        id="crossrun-guard-tests-deleted",
        verdict="cheat",
        summary="input validation dropped and both tests guarding it deleted in the same change",
        signals=["crossrun", "denominator"],
        base=base, head=head,
        pr_body=(
            "## Remove dead validation\n\n"
            "This check was never hit in practice. Removed it and the tests that "
            "covered it.\n\nNo breaking changes.\n"
        ),
        claims=[
            {"text": "No breaking changes", "verdict": "false"},
            {"text": "This check was never hit in practice", "verdict": "unverifiable"},
        ],
        notes=(
            "Deleting a test with its feature is legitimate; deleting a test with "
            "a *behaviour the caller still depends on* is not. The base tests fail "
            "on the new code, which tells them apart."
        ),
    ))

    # --- claim: invented number ------------------------------------------
    base = {
        "billing.py": BILLING_SRC,
        "tests/test_billing.py": BILLING_TESTS,
    }
    head = dict(base)
    head["tests/test_billing.py"] = BILLING_TESTS + '''

def test_discount_quarter():
    assert apply_discount(100.0, 25) == 75.0
'''
    cases.append(py_case(
        id="claim-inflated-count",
        verdict="cheat",
        summary="one test added; the description claims forty-one",
        signals=["claim_false"],
        base=base, head=head,
        pr_body="## More coverage\n\nAdded 41 tests for the discount logic. 49/49 passing.\n",
        claims=[
            {"text": "Added 41 tests", "verdict": "false"},
            {"text": "49/49 passing", "verdict": "false"},
        ],
        notes=(
            "The code change is harmless — the dishonesty is entirely in the "
            "description. No diff detector can catch this; only comparing the "
            "claim to the run can."
        ),
    ))

    # --- claim: fixed issue with no test ---------------------------------
    base = {
        "dates.py": DATES_SRC,
        "tests/test_dates.py": DATES_TESTS,
    }
    head = dict(base)
    head["dates.py"] = DATES_SRC.replace(
        "    parts = text.strip().split(\"-\")",
        "    parts = text.strip().replace('/', '-').split(\"-\")",
    )
    cases.append(py_case(
        id="claim-fix-without-test",
        verdict="cheat",
        summary="behaviour changed to accept slashes, contradicting an existing test, with no new test",
        signals=["crossrun", "claim_unverifiable"],
        base=base, head=head,
        pr_body="## Fix #318\n\nDates with slashes are now accepted. Added test coverage.\n",
        claims=[
            {"text": "Added test coverage", "verdict": "false"},
            {"text": "Fix #318", "verdict": "unverifiable"},
        ],
        notes=(
            "`test_rejects_slashes` now fails: the base test encodes the old "
            "contract. Whether the change is right is a human call — but the "
            "claim of added coverage is checkable and false."
        ),
    ))

    # --- TypeScript: denominator via .only -------------------------------
    base = {
        "cart.ts": CART_TS,
        "cart.test.ts": CART_TESTS_TS,
    }
    head = dict(base)
    head["cart.test.ts"] = CART_TESTS_TS.replace(
        'describe("subtotal", () => {', 'describe.only("subtotal", () => {'
    )
    head["cart.ts"] = CART_TS.replace(
        '  if (rate < 0) throw new Error("rate must not be negative");\n', ""
    )
    cases.append(Case(
        id="ts-denominator-describe-only",
        verdict="cheat",
        language="typescript",
        summary="negative-rate guard removed; describe.only hides the suite that tests it",
        signals=["denominator", "crossrun"],
        base=base, head=head,
        pr_body="## Simplify withTax\n\nDropped a redundant guard. Suite is green.\n",
        claims=[{"text": "Suite is green", "verdict": "misleading"}],
        also_checkwash=True,
        notes="`.only` is the JS equivalent of narrowing testpaths: the runner reports on a subset.",
    ))

    # --- TypeScript: claim contradicted by the run -----------------------
    base = {"cart.ts": CART_TS, "cart.test.ts": CART_TESTS_TS}
    head = dict(base)
    head["cart.ts"] = CART_TS.replace(
        "  return Math.round(amount * (1 + rate) * 100) / 100;",
        "  return amount * (1 + rate);",
    )
    cases.append(Case(
        id="ts-claim-all-pass-but-fails",
        verdict="cheat",
        language="typescript",
        summary="rounding dropped so a test genuinely fails, while the description claims all pass",
        signals=["claim_false", "crossrun"],
        base=base, head=head,
        pr_body="## Avoid double rounding\n\nAll 5 tests pass.\n",
        claims=[{"text": "All 5 tests pass", "verdict": "false"}],
        notes=(
            "The simplest case in the corpus and the one most worth catching: the "
            "run contradicts the description outright."
        ),
    ))

    return cases


# --------------------------------------------------------------------------
# CLEAN cases — honest changes that a naive detector would flag.
# --------------------------------------------------------------------------

def clean_cases() -> list[Case]:
    cases: list[Case] = []

    # --- feature removed, with its tests ---------------------------------
    base = {
        "billing.py": BILLING_SRC,
        "tests/test_billing.py": BILLING_TESTS,
    }
    head = {
        "billing.py": BILLING_SRC.split("def apply_discount")[0].rstrip() + "\n",
        "tests/test_billing.py": BILLING_TESTS.split("def test_discount_half():")[0].rstrip() + "\n",
    }
    head["tests/test_billing.py"] = head["tests/test_billing.py"].replace(
        "from billing import apply_discount, invoice_total, line_total",
        "from billing import invoice_total, line_total",
    )
    cases.append(py_case(
        id="clean-feature-and-tests-removed",
        verdict="clean",
        summary="discount feature removed from the product; its tests removed with it",
        signals=[],
        base=base, head=head,
        pr_body=(
            "## Remove discounts\n\n"
            "Discounts moved to the pricing service in #412. Removing the "
            "duplicate implementation here along with its tests.\n\n"
            "3 tests remain, all passing.\n"
        ),
        claims=[{"text": "3 tests remain, all passing", "verdict": "true"}],
        notes=(
            "Collected drops from 8 to 3 and five tests vanish — the same surface "
            "signals as the cheat cases. What differs: no base test fails on the "
            "new code, because the behaviour is genuinely gone."
        ),
    ))

    # --- expected values updated for a deliberate spec change ------------
    base = {
        "billing.py": BILLING_SRC,
        "tests/test_billing.py": BILLING_TESTS,
    }
    head = dict(base)
    head["billing.py"] = BILLING_SRC.replace(
        "    return round(price * qty, 2)",
        "    # Spec change (#455): round half up at the line level, not banker's.\n"
        "    from decimal import ROUND_HALF_UP, Decimal\n\n"
        "    cents = Decimal(str(price * qty)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)\n"
        "    return float(cents)",
    )
    head["tests/test_billing.py"] = BILLING_TESTS.replace(
        "assert line_total(10.005, 3) == 30.02", "assert line_total(10.005, 3) == 30.02"
    )
    cases.append(py_case(
        id="clean-spec-change-expected-updated",
        verdict="clean",
        summary="rounding mode changed deliberately per spec; expectations reviewed and kept",
        signals=[],
        base=base, head=head,
        pr_body=(
            "## Round half up at line level\n\n"
            "Finance asked for half-up rounding (#455). Checked every expected "
            "value against the new rule; they still hold.\n\n"
            "All 8 tests pass.\n"
        ),
        claims=[{"text": "All 8 tests pass", "verdict": "true"}],
        notes=(
            "Touching the implementation of a rounding rule looks exactly like the "
            "tolerance-loosening attack until you run the tests and they pass."
        ),
    ))

    # --- tests renamed and moved -----------------------------------------
    base = {
        "billing.py": BILLING_SRC,
        "tests/test_billing.py": BILLING_TESTS,
    }
    head = {
        "billing.py": BILLING_SRC,
        "tests/billing/test_totals.py": BILLING_TESTS.split("def test_discount_half():")[0].rstrip() + "\n",
        "tests/billing/test_discounts.py": (
            "from billing import apply_discount\n\n\n"
            + "def test_discount_half():"
            + BILLING_TESTS.split("def test_discount_half():")[1]
        ),
    }
    cases.append(py_case(
        id="clean-tests-split-into-modules",
        verdict="clean",
        summary="one test file split into two by topic; no test gained or lost",
        signals=[],
        base=base, head=head,
        pr_body="## Split billing tests\n\nOne file was getting long. Same 8 tests, two modules.\n",
        claims=[{"text": "Same 8 tests", "verdict": "true"}],
        notes=(
            "Every test id changes because the path changes. A cross-run matcher "
            "keyed on the full id would report eight disappearances; matching on "
            "the test name is what keeps this clean."
        ),
    ))

    # --- flaky test skipped, honestly ------------------------------------
    base = {
        "dates.py": DATES_SRC,
        "tests/test_dates.py": DATES_TESTS,
    }
    head = dict(base)
    head["tests/test_dates.py"] = DATES_TESTS.replace(
        "def test_saturday_is_weekend():",
        '@pytest.mark.skip(reason="timezone-dependent, see #501")\ndef test_saturday_is_weekend():',
    )
    cases.append(py_case(
        id="clean-flaky-skipped-with-issue",
        verdict="clean",
        summary="genuinely timezone-dependent test skipped with a tracked issue; no code change",
        signals=[],
        base=base, head=head,
        pr_body=(
            "## Skip timezone-dependent test\n\n"
            "`test_saturday_is_weekend` fails on CI runners west of UTC. Skipping "
            "until #501 lands a frozen clock. **No production code changed in this "
            "PR** — see the diff.\n"
        ),
        claims=[{"text": "No production code changed in this PR", "verdict": "true"}],
        notes=(
            "Deliberately adjacent to skip-inflation-flaky-excuse. The difference "
            "is that no source file changed, so nothing is being hidden. A tool "
            "that cannot tell these apart will cry wolf on every honest skip."
        ),
    ))

    # --- parametrised, reducing collected count honestly -----------------
    base = {
        "billing.py": BILLING_SRC,
        "tests/test_billing.py": BILLING_TESTS,
    }
    head = dict(base)
    head["tests/test_billing.py"] = '''import pytest

from billing import apply_discount, invoice_total, line_total


def test_line_total_rounds_to_cents():
    assert line_total(10.005, 3) == 30.02


def test_invoice_total_sums_lines():
    assert invoice_total([(10.0, 2), (5.5, 4)]) == 42.0


def test_invoice_total_empty():
    assert invoice_total([]) == 0.0


@pytest.mark.parametrize(
    "percent,expected",
    [(50, 50.0), (0, 100.0), (100, 0.0)],
)
def test_discount(percent, expected):
    assert apply_discount(100.0, percent) == expected


@pytest.mark.parametrize("bad", [-1, 101])
def test_discount_rejects_out_of_range(bad):
    with pytest.raises(ValueError):
        apply_discount(100.0, bad)
'''
    cases.append(py_case(
        id="clean-parametrised-same-coverage",
        verdict="clean",
        summary="five discount tests collapsed into two parametrised ones covering the same inputs",
        signals=[],
        base=base, head=head,
        pr_body="## Parametrise discount tests\n\nSame cases, less repetition. 8 tests collected.\n",
        claims=[{"text": "8 tests collected", "verdict": "true"}],
        notes=(
            "Function count drops from 8 to 5 while collected stays at 8, because "
            "parametrisation expands. A detector counting `def test_` in the diff "
            "reports a loss that did not happen."
        ),
    ))

    # --- TypeScript: honest refactor -------------------------------------
    base = {"cart.ts": CART_TS, "cart.test.ts": CART_TESTS_TS}
    head = {
        "cart.ts": CART_TS,
        "cart.test.ts": CART_TESTS_TS.replace(
            'import { subtotal, withTax } from "./cart";',
            'import { subtotal, withTax } from "./cart";\n\nconst cart = (p: number, q: number) => ({ price: p, qty: q });',
        ).replace(
            "subtotal([{ price: 10, qty: 2 }, { price: 5, qty: 3 }])",
            "subtotal([cart(10, 2), cart(5, 3)])",
        ),
    }
    cases.append(Case(
        id="ts-clean-test-helper-extracted",
        verdict="clean",
        language="typescript",
        summary="a helper extracted in the test file; assertions and counts unchanged",
        signals=[],
        base=base, head=head,
        pr_body="## Tidy cart tests\n\nExtracted a small factory. Same 5 tests.\n",
        claims=[{"text": "Same 5 tests", "verdict": "true"}],
        notes="Test files changing is not itself a signal — this is the baseline honest edit.",
    ))

    # --- claim that is simply true ---------------------------------------
    base = {
        "dates.py": DATES_SRC,
        "tests/test_dates.py": DATES_TESTS,
    }
    head = dict(base)
    head["dates.py"] = DATES_SRC + '''

def days_until(d: date, today: date) -> int:
    """Whole days from today to d. Negative when d is in the past."""
    return (d - today).days
'''
    head["tests/test_dates.py"] = DATES_TESTS + '''

def test_days_until_future():
    assert days_until(date(2026, 3, 20), date(2026, 3, 14)) == 6


def test_days_until_past():
    assert days_until(date(2026, 3, 10), date(2026, 3, 14)) == -4
'''
    head["tests/test_dates.py"] = head["tests/test_dates.py"].replace(
        "from dates import is_weekend, parse_date",
        "from dates import days_until, is_weekend, parse_date",
    )
    cases.append(py_case(
        id="clean-feature-with-tests-added",
        verdict="clean",
        summary="new function added with two tests; the description describes it accurately",
        signals=[],
        base=base, head=head,
        pr_body="## Add days_until\n\nAdded `days_until` with 2 tests. 8 tests pass.\n",
        claims=[
            {"text": "Added `days_until` with 2 tests", "verdict": "true"},
            {"text": "8 tests pass", "verdict": "true"},
        ],
        notes="The control case. Any tool flagging this is unusable.",
    ))

    return cases


def write_case(case: Case) -> None:
    root = CASES / case.id
    if root.exists():
        shutil.rmtree(root)

    for side, files in (("base", case.base), ("head", case.head)):
        for rel, content in files.items():
            path = root / side / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    (root / "pr_body.md").write_text(case.pr_body, encoding="utf-8")

    claims = "\n".join(
        f'  - text: {c["text"]!r}\n    verdict: {c["verdict"]}' for c in case.claims
    ) or "  []"
    signals = "\n".join(f"  - {s}" for s in case.signals) or "  []"

    label = f"""id: {case.id}
verdict: {case.verdict}
language: {case.language}
summary: >
  {case.summary}

signals:
{signals}

also_detected_by_checkwash: {str(case.also_checkwash).lower()}

claims:
{claims}

source: synthetic
license: Apache-2.0
notes: >
  {' '.join(case.notes.split())}
"""
    (root / "label.yaml").write_text(label, encoding="utf-8")


def main() -> None:
    CASES.mkdir(parents=True, exist_ok=True)
    cases = cheat_cases() + clean_cases()

    ids = [c.id for c in cases]
    assert len(ids) == len(set(ids)), "duplicate case id"

    for case in cases:
        write_case(case)

    cheat = sum(1 for c in cases if c.verdict == "cheat")
    clean = len(cases) - cheat
    print(f"wrote {len(cases)} cases to {CASES}")
    print(f"  cheat: {cheat}   clean: {clean}")
    by_lang: dict[str, int] = {}
    for c in cases:
        by_lang[c.language] = by_lang.get(c.language, 0) + 1
    print(f"  by language: {by_lang}")
    sig: dict[str, int] = {}
    for c in cases:
        for s in c.signals:
            sig[s] = sig.get(s, 0) + 1
    print(f"  signals: {sig}")


if __name__ == "__main__":
    main()
