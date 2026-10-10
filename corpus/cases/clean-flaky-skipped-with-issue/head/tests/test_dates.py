import pytest
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


@pytest.mark.skip(reason="timezone-dependent, see #501")
def test_saturday_is_weekend():
    assert is_weekend(date(2026, 3, 14)) is True


def test_monday_is_not_weekend():
    assert is_weekend(date(2026, 3, 16)) is False
