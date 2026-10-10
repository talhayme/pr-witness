"""Invoice arithmetic."""


def line_total(price: float, qty: int) -> float:
    return round(price * qty, 2)


def invoice_total(lines: list[tuple[float, int]]) -> float:
    return round(sum(line_total(p, q) for p, q in lines), 2)


def apply_discount(total: float, percent: float) -> float:
    if not 0 <= percent <= 100:
        raise ValueError("percent must be between 0 and 100")
    return round(total * (1 - percent / 100), 2)
