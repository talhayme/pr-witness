import pytest
from app import checked


@pytest.mark.parametrize("bad", [-1, 101])
def test_invalid(bad):
    with pytest.raises(ValueError):
        checked(bad)


@pytest.mark.parametrize("ok", [50])
def test_valid(ok):
    assert checked(ok) == ok
