"""Invoice arithmetic."""


def line_total(price: float, qty: int) -> float:
    return round(price * qty, 2)


def invoice_total(lines: list[tuple[float, int]]) -> float:
    return round(sum(line_total(p, q) for p, q in lines), 2)
