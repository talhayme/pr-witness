from billing import apply_discount


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
