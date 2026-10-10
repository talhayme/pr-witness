"""Invoice arithmetic."""


def line_total(price: float, qty: int) -> float:
    # Spec change (#455): round half up at the line level, not banker's.
    from decimal import ROUND_HALF_UP, Decimal

    cents = Decimal(str(price * qty)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return float(cents)


def invoice_total(lines: list[tuple[float, int]]) -> float:
    return round(sum(line_total(p, q) for p, q in lines), 2)


def apply_discount(total: float, percent: float) -> float:
    if not 0 <= percent <= 100:
        raise ValueError("percent must be between 0 and 100")
    return round(total * (1 - percent / 100), 2)
