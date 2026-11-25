import json
import unittest
from unittest.mock import patch, call
import resource
from typing import Callable, Type

import pytest

from ..testers.specs import TestSpecs
from ..testers.tester import Tester, Test, TestError


class MockTester(Tester):
    def __init__(
        self,
        specs: TestSpecs,
        test_class: Type[Test] | None = Test,
        resource_settings: list[tuple[int, tuple[int, int]]] | None = None,
    ) -> None:
        super().__init__(specs, test_class, resource_settings)

    def run(self) -> None:
        pass


class TestResourceLimits(unittest.TestCase):

    @patch("resource.setrlimit")
    def test_set_resource_limits_single_limit(self, mock_setrlimit):
        """Test setting a single resource limit."""
        # Arrange
        tester = MockTester(specs=TestSpecs(), resource_settings=[(resource.RLIMIT_CPU, (10, 20))])

        # Act
        tester.set_resource_limits(tester.resource_settings)

        # Assert
        mock_setrlimit.assert_called_once_with(resource.RLIMIT_CPU, (10, 20))

    @patch("resource.setrlimit")
    def test_set_resource_limits_multiple_limits(self, mock_setrlimit):
        """Test setting multiple resource limits."""
        # Arrange
        tester = MockTester(
            specs=TestSpecs(),
            resource_settings=[
                (resource.RLIMIT_CPU, (10, 20)),
                (resource.RLIMIT_NOFILE, (1024, 2048)),
                (resource.RLIMIT_AS, (1024 * 1024 * 100, 1024 * 1024 * 200)),
            ],
        )

        # Act
        tester.set_resource_limits(tester.resource_settings)

        # Assert
        expected_calls = [
            call(resource.RLIMIT_CPU, (10, 20)),
            call(resource.RLIMIT_NOFILE, (1024, 2048)),
            call(resource.RLIMIT_AS, (1024 * 1024 * 100, 1024 * 1024 * 200)),
        ]
        mock_setrlimit.assert_has_calls(expected_calls, any_order=False)
        self.assertEqual(mock_setrlimit.call_count, 3)


class MockTest(Test):
    def __init__(self, tester: Tester, name: str = "test 1", result: Callable | None = None) -> None:
        self._name = name
        self._result = result
        self.calls = []
        super().__init__(tester)

    @property
    def test_name(self) -> str:
        return super().test_name or self._name

    def before_test_run(self) -> None:
        self.calls.append("before")

    def after_successful_test_run(self) -> None:
        self.calls.append("after")

    @Test.run_decorator
    def run(self) -> str:
        return self._result(self)


def _result(result_json: str) -> dict:
    return json.loads(result_json)


@pytest.fixture
def tester():
    return MockTester(specs=TestSpecs({"points": {"test 1": 4}}))


@pytest.fixture
def test(tester):
    return MockTest(tester)


class TestTestPoints:
    def test_points_from_specs(self, test):
        assert test.points_total == 4

    def test_default_points(self):
        assert MockTest(MockTester(specs=TestSpecs())).points_total == 1

    def test_non_positive_points(self):
        with pytest.raises(ValueError, match="must be > 0"):
            MockTest(MockTester(specs=TestSpecs({"points": {"test 1": 0}})))


class TestFormatResult:
    def test_format(self):
        assert _result(Test.format_result("t", Test.Status.PASS, "out", 1, 2, time=3)) == {
            "name": "t",
            "output": "out",
            "marks_earned": 1,
            "marks_total": 2,
            "status": "pass",
            "time": 3,
        }

    @pytest.mark.parametrize(
        "points_earned, points_total, time, message",
        [
            pytest.param(1, -1, None, "total points must be >= 0", id="negative total"),
            pytest.param(-1, 1, None, "points earned must be >= 0", id="negative earned"),
            pytest.param(1, 1, -1, "time must be a positive integer", id="negative time"),
            pytest.param(1, 1, 1.5, "time must be a positive integer", id="non-integer time"),
        ],
    )
    def test_invalid(self, points_earned, points_total, time, message):
        with pytest.raises(ValueError, match=message):
            Test.format_result("t", Test.Status.PASS, "", points_earned, points_total, time)

    def test_format_annotations(self):
        assert _result(Test.format_annotations([{"line": 1}])) == {"annotations": [{"line": 1}]}

    def test_format_overall_comment_str(self):
        assert _result(Test.format_overall_comment("good")) == {"overall_comment": "good"}

    def test_format_overall_comment_iterable(self):
        assert _result(Test.format_overall_comment(["a", "b"], separator="|")) == {"overall_comment": "a|b"}

    def test_format_extra_marks(self):
        assert _result(Test.format_extra_marks([{"mark": 1}])) == {"extra_marks": [{"mark": 1}]}

    def test_format_tags(self):
        assert _result(Test.format_tags(["a", {"name": "b", "description": "c"}])) == {
            "tags": [{"name": "a"}, {"name": "b", "description": "c"}]
        }


class TestTestOutcomes:
    def test_passed(self, test):
        assert _result(test.passed("yay")) == {
            "name": "test 1",
            "output": "yay",
            "marks_earned": 4,
            "marks_total": 4,
            "status": "pass",
            "time": None,
        }

    def test_passed_with_bonus(self, test):
        result = _result(test.passed_with_bonus(2))
        assert (result["status"], result["marks_earned"]) == ("pass", 6)

    def test_passed_with_negative_bonus(self, test):
        with pytest.raises(ValueError, match="bonus points must be >= 0"):
            test.passed_with_bonus(-1)

    def test_partially_passed(self, test):
        result = _result(test.partially_passed(2, "half"))
        assert (result["status"], result["marks_earned"], result["output"]) == ("partial", 2, "half")

    @pytest.mark.parametrize("points", [0, 4])
    def test_partially_passed_out_of_range(self, test, points):
        with pytest.raises(ValueError):
            test.partially_passed(points, "")

    def test_failed(self, test):
        result = _result(test.failed("no"))
        assert (result["status"], result["marks_earned"], result["output"]) == ("fail", 0, "no")

    def test_error(self, test):
        result = _result(test.error("broken"))
        assert (result["status"], result["marks_earned"], result["output"]) == ("error", 0, "broken")

    @pytest.mark.parametrize(
        "points, status, earned",
        [(-1, "fail", 0), (0, "fail", 0), (2, "partial", 2), (4, "pass", 4), (5, "pass", 5)],
    )
    def test_done(self, test, points, status, earned):
        result = _result(test.done(points))
        assert (result["status"], result["marks_earned"]) == (status, earned)


class TestTestRunDecorator:
    def test_success(self, tester):
        test = MockTest(tester, result=lambda t: t.passed())
        assert _result(test.run())["status"] == "pass"
        assert test.calls == ["before", "after"]

    def test_test_error(self, tester):
        def result(_test):
            raise TestError("expected problem")

        test = MockTest(tester, result=result)
        output = _result(test.run())
        assert (output["status"], output["output"]) == ("error", "expected problem")
        assert test.calls == ["before"]

    def test_unexpected_error(self, tester):
        def result(_test):
            raise RuntimeError("unexpected problem")

        output = _result(MockTest(tester, result=result).run())
        assert output["status"] == "error"
        assert "Traceback" in output["output"]
        assert "unexpected problem" in output["output"]


class RunningTester(MockTester):
    def __init__(self, run_func: Callable, **kwargs) -> None:
        super().__init__(specs=TestSpecs(), **kwargs)
        self.run_func = run_func
        self.calls = []

    def after_tester_run(self) -> None:
        self.calls.append("after")

    @Tester.run_decorator
    def run(self) -> None:
        return self.run_func()


class TestTesterRun:
    def test_success(self):
        tester = RunningTester(lambda: "done")
        assert tester.run() == "done"
        assert tester.calls == ["after"]

    def test_sets_resource_limits(self):
        with patch("resource.setrlimit") as mock_setrlimit:
            RunningTester(lambda: None, resource_settings=[(resource.RLIMIT_CPU, (1, 2))]).run()
        mock_setrlimit.assert_called_once_with(resource.RLIMIT_CPU, (1, 2))

    def test_test_error(self, capsys):
        def run():
            raise TestError("expected problem")

        tester = RunningTester(run)
        tester.run()
        output = _result(capsys.readouterr().out)
        assert (output["name"], output["status"], output["output"]) == ("All tests", "error", "expected problem")
        assert tester.calls == ["after"]

    def test_unexpected_error(self, capsys):
        def run():
            raise RuntimeError("unexpected problem")

        tester = RunningTester(run)
        tester.run()
        output = _result(capsys.readouterr().out)
        assert output["status"] == "error_all"
        assert "unexpected problem" in output["output"]
        assert tester.calls == ["after"]

    def test_error_all(self):
        assert _result(Tester.error_all("msg", points_total=3, expected=True)) == {
            "name": "All tests",
            "output": "msg",
            "marks_earned": 0,
            "marks_total": 3,
            "status": "error",
            "time": None,
        }
