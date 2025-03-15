from __future__ import annotations

import json
from abc import ABC, abstractmethod
from functools import wraps
from typing import Optional, Callable, Any, Type, Dict, Iterable, List
from .specs import TestSpecs
import traceback
import resource


class TestError(Exception):
    """Error raised when a test error occurs"""


class Test(ABC):
    class Status:
        PASS: str = "pass"
        PARTIAL: str = "partial"
        FAIL: str = "fail"
        ERROR: str = "error"
        ERROR_ALL: str = "error_all"

    @abstractmethod
    def __init__(self, tester: "Tester") -> None:
        """Initialize a Test"""
        self.tester = tester
        self.points_total = self.get_total_points()
        if self.points_total <= 0:
            raise ValueError("The test total points must be > 0")

    @property
    @abstractmethod
    def test_name(self) -> str:
        """
        Returns a unique name for the test.
        """
        pass

    def get_total_points(self) -> int:
        """Return the total possible points for this test"""
        return self.tester.specs.get("points", default={}).get(self.test_name, 1)

    @staticmethod
    def format_result(
        test_name: str,
        status: str,
        output: str,
        points_earned: int,
        points_total: int,
        time: Optional[int] = None,
    ) -> str:
        """
        Formats a test result.
        :param test_name: The test name
        :param status: A member of Test.Status.
        :param output: The test output.
        :param points_earned: The points earned by the test, must be a float >= 0 (can be greater than the test total
                              points when assigning bonus points).
        :param points_total: The total points the test could earn, must be a float >= 0.
        :param time: The time it took to run the test, can be None
        :return The formatted test result.
        """
        if points_total < 0:
            raise ValueError("The test total points must be >= 0")
        if points_earned < 0:
            raise ValueError("The test points earned must be >= 0")
        if time is not None:
            if not isinstance(time, int) or time < 0:
                raise ValueError("The time must be a positive integer or None")

        result_json = json.dumps(
            {
                "name": test_name,
                "output": output,
                "marks_earned": points_earned,
                "marks_total": points_total,
                "status": status,
                "time": time,
            }
        )
        return result_json

    def format(self, status: str, output: str, points_earned: int) -> str:
        """
        Formats the result of this test.
        :param status: A member of Test.Status.
        :param output: The test output.
        :param points_earned: The points earned by the test, must be a float >= 0 (can be greater than the test total
                              points when assigning bonus points).
        :return The formatted test result.
        """
        return Test.format_result(self.test_name, status, output, points_earned, self.points_total)

    @staticmethod
    def format_annotations(annotation_data: List[Dict[str, Any]]) -> str:
        """
        Formats annotation data.
        :param annotation_data: a dictionary containing annotation data
        :return a json string representation of the annotation data.
        """
        return json.dumps({"annotations": annotation_data})

    @staticmethod
    def format_overall_comment(overall_comment_data: str | Iterable[str], separator: str = "\n\n") -> str:
        """
        Formats overall comment data.
        :param overall_comment_data: the contents of the overall comment
        :param separator: if overall_comment_data is a collection, use separator to join the elements
        :return a json string representation of the tag data.
        """
        if isinstance(overall_comment_data, str):
            content = overall_comment_data
        else:
            content = separator.join(overall_comment_data)
        return json.dumps({"overall_comment": content})

    @staticmethod
    def format_tags(tag_data: Iterable[str | dict[str, str]]) -> str:
        """
        Formats tag data.
        :param tag_data: an iterable of tag data. Each element is either a tag name (str) or a dictionary with
            keys "name" and "description".
        :return a json string representation of the tag data.
        """
        tag_list = []
        for tag in tag_data:
            if isinstance(tag, str):
                tag_list.append({"name": tag})
            else:
                tag_list.append(tag)
        return json.dumps({"tags": tag_list})

    def passed_with_bonus(self, points_bonus: int, message: str = "") -> str:
        """
        Passes this test earning bonus points in addition to the test total points. If a feedback file is enabled, adds
        feedback to it.
        :param points_bonus: The bonus points, must be an int >= 0.
        :param message: An optional message, will be shown as test output.
        :return The formatted passed test.
        """
        if points_bonus < 0:
            raise ValueError("The test bonus points must be >= 0")
        result = self.format(
            status=self.Status.PASS,
            output=message,
            points_earned=self.points_total + points_bonus,
        )
        return result

    def passed(self, message: str = "") -> str:
        """
        Passes this test earning the test total points. If a feedback file is enabled, adds feedback to it.
        :param message: An optional message, will be shown as test output.
        :return The formatted passed test.
        """
        result = self.format(status=self.Status.PASS, output=message, points_earned=self.points_total)
        return result

    def partially_passed(self, points_earned: int, message: str) -> str:
        """
        Partially passes this test with some points earned. If a feedback file is enabled, adds feedback to it.
        :param points_earned: The points earned by the test, must be an int > 0 and < the test total points.
        :param message: The message explaining why the test was not fully passed, will be shown as test output.
        :return The formatted partially passed test.
        """
        if points_earned <= 0:
            raise ValueError("The test points earned must be > 0")
        if points_earned >= self.points_total:
            raise ValueError("The test points earned must be < the test total points")
        result = self.format(status=self.Status.PARTIAL, output=message, points_earned=points_earned)
        return result

    def failed(
        self,
        message: str,
    ) -> str:
        """
        Fails this test with 0 points earned. If a feedback file is enabled, adds feedback to it.
        :param message: The failure message, will be shown as test output.
        :return The formatted failed test.
        """
        result = self.format(status=self.Status.FAIL, output=message, points_earned=0)
        return result

    def done(self, points_earned: int, message: str = "") -> str:
        """
        Passes, partially passes or fails this test depending on the points earned. If the points are <= 0 this test is
        failed with 0 points earned, if the points are >= test total points this test is passed earning the test total
        points (plus the possible bonus), otherwise this test is partially passed. If a feedback file is enabled, adds
        feedback to it.
        :param points_earned: The points earned by the test.
        :param message: The optional message explaining the test outcome, will be shown as test output.
        :return The formatted test.
        """
        if points_earned <= 0:
            return self.failed(message)
        elif points_earned == self.points_total:
            return self.passed(message)
        elif points_earned > self.points_total:
            points_bonus = points_earned - self.points_total
            return self.passed_with_bonus(points_bonus, message)
        else:
            return self.partially_passed(points_earned, message)

    def error(self, message: str) -> str:
        """
        Err this test. If a feedback file is enabled, adds feedback to it.
        :param message: The error message, will be shown as test output.
        :return The formatted erred test.
        """
        result = self.format(status=self.Status.ERROR, output=message, points_earned=0)
        return result

    def before_test_run(self) -> None:
        """
        Callback invoked before running a test.
        Use this for test initialization steps that can fail, rather than using test_class.__init__().
        """

    def after_successful_test_run(self) -> None:
        """
        Callback invoked after successfully running a test.
        Use this to access test data in the tester. Don't use this for test cleanup steps, use test_class.run() instead.
        """

    @staticmethod
    def run_decorator(run_func: Callable) -> Callable:
        """
        Wrapper around a test.run method. Used to print error messages
        in the correct json format. If it catches a TestError then
        only the error message is sent in the description, otherwise the
        whole traceback is sent.
        """

        @wraps(run_func)
        def run_func_wrapper(self, *args: Any, **kwargs: Any) -> str:
            try:
                # if a test __init__ fails it should really stop the whole tester, we don't have enough
                # info to continue safely, e.g. the total points (which skews the student mark)
                self.before_test_run()
                result_json = run_func(self, *args, **kwargs)
                self.after_successful_test_run()
            except TestError as e:
                result_json = self.error(message=str(e))
            except Exception as e:
                result_json = self.error(message=f"{traceback.format_exc()}\n{e}")
            return result_json

        return run_func_wrapper

    @abstractmethod
    def run(self) -> None:
        """
        Runs this test.
        :return The formatted test.
        """


class Tester(ABC):
    @abstractmethod
    def __init__(
        self,
        specs: TestSpecs,
        test_class: Optional[Type[Test]] = Test,
        resource_settings: list[tuple[int, tuple[int, int]]] | None = None,
    ) -> None:
        self.specs = specs
        self.test_class = test_class

        if resource_settings is None:
            self.resource_settings = []
        else:
            self.resource_settings = resource_settings

    @staticmethod
    def error_all(message: str, points_total: int = 0, expected: bool = False) -> str:
        """
        Err all tests of this tester with a single message.
        :param message: The error message.
        :param points_total: The total points the tests could earn, must be a float >= 0.
        :param expected: Indicates whether this reports an expected or an unexpected tester error.
        :return The formatted erred tests.
        """
        status = Test.Status.ERROR if expected else Test.Status.ERROR_ALL
        return Test.format_result(
            test_name="All tests",
            status=status,
            output=message,
            points_earned=0,
            points_total=points_total,
        )

    def before_tester_run(self) -> None:
        """
        Callback invoked before running this tester.
        Use this for tester initialization steps that can fail, rather than using __init__.
        """
        self.set_resource_limits(self.resource_settings)

    def after_tester_run(self) -> None:
        """
        Callback invoked after running this tester, including in case of exceptions.
        Use this for tester cleanup steps that should always be executed, regardless of errors.
        """

    @staticmethod
    def set_resource_limits(resource_settings: list[tuple[int, tuple[int, int]]]) -> None:
        """Sets system resource limits using the `resource` package."""
        for resource_name, rlimit in resource_settings:
            resource.setrlimit(resource_name, rlimit)

    @staticmethod
    def run_decorator(run_func: Callable) -> Callable:
        """
        Wrapper around a tester.run method. Used to print error messages
        in the correct json format. If it catches a TestError then
        only the error message is sent in the description, otherwise the
        whole traceback is sent.
        """

        @wraps(run_func)
        def run_func_wrapper(self, *args: Any, **kwargs: Any) -> None:
            try:
                self.before_tester_run()
                return run_func(self, *args, **kwargs)
            except TestError as e:
                print(Tester.error_all(message=str(e), expected=True), flush=True)
            except Exception as e:
                print(
                    Tester.error_all(message=f"{traceback.format_exc()}\n{e}"),
                    flush=True,
                )
            finally:
                self.after_tester_run()

        return run_func_wrapper

    @abstractmethod
    def run(self) -> None:
        """
        Runs all tests in this tester.
        """
