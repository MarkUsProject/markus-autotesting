import pytest


@pytest.mark.parametrize("marks_earned", [0, 1, 2])
def test_partial_marks(request, marks_earned: int) -> None:
    request.node.add_marker(pytest.mark.markus_marks_total(2))
    request.node.add_marker(pytest.mark.markus_marks_earned(marks_earned))
    assert False, f"Should be {marks_earned}/2"
