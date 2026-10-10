"""Date parsing with a deliberately narrow contract."""

from datetime import date


def parse_date(text: str) -> date:
    """Parse YYYY-MM-DD. Raises ValueError on anything else."""
    parts = text.strip().replace('/', '-').split("-")
    if len(parts) != 3:
        raise ValueError(f"expected YYYY-MM-DD, got {text!r}")
    year, month, day = (int(p) for p in parts)
    return date(year, month, day)


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5
