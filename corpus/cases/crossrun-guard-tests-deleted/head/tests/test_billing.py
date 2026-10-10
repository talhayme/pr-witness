from billing import apply_discount, invoice_total, line_total


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
