import pytest


def add_one(x):
    return x + 1


@pytest.mark.skip
def test_add_one():
    assert add_one(1) == 2
