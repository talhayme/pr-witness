import pytest
from app import checked


def test_negative():
    with pytest.raises(ValueError):
        checked(-1)


def test_large():
    with pytest.raises(ValueError):
        checked(101)


def test_ok():
    assert checked(50) == 50
