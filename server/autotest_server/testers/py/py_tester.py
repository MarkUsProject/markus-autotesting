import os
import unittest
from typing import TextIO, Tuple, Optional, Type, Dict, List
from types import TracebackType
import pytest
import sys
from ..tester import Tester, Test
import uuid
from ..specs import TestSpecs


class TextTestResults(unittest.TextTestResult):
    """
    Custom unittest.TextTestResult that saves results as
    a hash to self.results so they can be more easily
    parsed by the PyTest.run function
    """

    def __init__(self, stream: TextIO, descriptions: bool, verbosity: int) -> None:
        """
        Extends TextTestResult.__init__ and adds additional attributes to keep track
        of successes and additional result information.
        """
        super().__init__(stream, descriptions, verbosity)
        self.results = []
        self.successes = []

    def addSuccess(self, test: unittest.TestCase) -> None:
        """
        Record that a test passed.
        """
        self.results.append(
            {
                "status": "success",
                "name": self._format_test_name(test),
                "errors": "",
                "description": test._testMethodDoc,
            }
        )
        self.successes.append(test)

    def addFailure(
        self,
        test: unittest.TestCase,
        err: Tuple[Optional[Type[BaseException]], Optional[BaseException], Optional[TracebackType]],
    ) -> None:
        """
        Record that a test failed.
        """
        super().addFailure(test, err)
        self.results.append(
            {
                "status": "failure",
                "name": self._format_test_name(test),
                "errors": self.failures[-1][-1],
                "description": test._testMethodDoc,
            }
        )

    def addError(
        self,
        test: unittest.TestCase,
        err: Tuple[Optional[Type[BaseException]], Optional[BaseException], Optional[TracebackType]],
    ) -> None:
        """
        Record that a test failed with an error.
        """
        super().addError(test, err)
        self.results.append(
            {
                "status": "error",
                "name": self._format_test_name(test),
                "errors": self.errors[-1][-1],
                "description": test._testMethodDoc,
            }
        )

    def _format_test_name(self, test: unittest.TestCase) -> str:
        full_id = test.id()
        parts = full_id.split(".")

        if len(parts) < 3:
            # Not enough parts to extract module/class/method structure
            return full_id

        try:
            module_path = "/".join(parts[:-2]) + ".py"
            return f"[{module_path}] {parts[-2]}.{parts[-1]}"
        except (IndexError, TypeError):
            return full_id


class PytestPlugin:
    """
    Pytest plugin to collect and parse test results as well
    as any errors during the test collection process.
    """

    def __init__(self) -> None:
        """
        Initialize a pytest plugin for collecting results
        """
        self.results = {}
        self.tags = set()
        self.annotations = []
        self.extra_marks = []
        self.overall_comments = []

    def pytest_configure(self, config):
        """Register custom markers for use with MarkUs."""
        config.addinivalue_line("markers", "markus_tag(name): indicate that the submission should be given a tag")
        config.addinivalue_line(
            "markers", "markus_annotation(**ann_data): indicate that the submission should be given an annotation"
        )
        config.addinivalue_line(
            "markers",
            "markus_overall_comments(comment): indicate that the submission should be given an overall comment",
        )
        config.addinivalue_line(
            "markers",
            "markus_message(text): indicate text that is displayed as part of the test output (even on success)",
        )
        config.addinivalue_line(
            "markers",
            "markus_extra_marks(mark, description, unit): add extra marks with custom description",
        )

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_runtest_makereport(self, item, call):
        """
        Implement a pytest hook that is run when reporting the
        results of a given test item.

        Records the results of each test in the self.results
        attribute.

        See pytest documentation for a description of the parameter
        types and the return value.
        """
        outcome = yield
        rep = outcome.get_result()
        if rep.failed or (item.nodeid not in self.results and not rep.skipped and rep.when != "teardown"):
            self.results[item.nodeid] = {
                "status": "failure" if rep.failed else "success",
                "name": self._format_test_name(item),
                "errors": str(rep.longrepr) if rep.failed else "",
                "description": item.obj.__doc__,
            }

        # Only check markers at the end of the test case
        if not rep.skipped and rep.when == "teardown":
            self._process_markers(item)

        return rep

    def _process_markers(self, item):
        """Process all markers for the given item.

        This looks for custom markers used to represent test metadata for MarkUs.
        """
        for marker in item.iter_markers():
            if marker.name == "markus_tag":
                if len(marker.args) > 0:
                    self.tags.add(marker.args[0].strip())
                elif "name" in marker.kwargs:
                    self.tags.add(marker.kwargs["name"].strip())
            elif marker.name == "markus_annotation":
                self.annotations.append(marker.kwargs)
            elif marker.name == "markus_overall_comments":
                if len(marker.args) > 0:
                    self.overall_comments.append(marker.args[0])
                elif "comment" in marker.kwargs:
                    self.overall_comments.append(marker.kwargs["comment"])
            elif marker.name == "markus_message" and marker.args != [] and item.nodeid in self.results:
                if self.results[item.nodeid].get("errors"):
                    self.results[item.nodeid]["errors"] += f"\n\n{marker.args[0]}"
                else:
                    self.results[item.nodeid]["errors"] = marker.args[0]
            elif marker.name == "markus_marks_total" and marker.args != [] and item.nodeid in self.results:
                self.results[item.nodeid]["marks_total"] = marker.args[0]
            elif marker.name == "markus_marks_earned" and marker.args != [] and item.nodeid in self.results:
                self.results[item.nodeid]["marks_earned"] = marker.args[0]
            elif marker.name == "markus_extra_marks" and marker.args != [] and item.nodeid in self.results:
                extra_mark = {
                    "id": str(uuid.uuid4()),
                    "mark": marker.args[0],
                    "fn": item.nodeid,
                    "description": marker.args[1],
                    "unit": marker.args[2] if len(marker.args) > 2 else "points",
                }
                self.extra_marks.append(extra_mark)

    def pytest_collectreport(self, report):
        """
        Implement a pytest hook that is run after the collector has
        finished collecting all tests.

        Records a test failure in the self.results attribute if the
        collection step failed.

        See pytest documentation for a description of the parameter
        types and the return value.
        """
        if report.failed:
            self.results[report.nodeid] = {
                "status": "error",
                "name": self._format_test_name(report),
                "errors": str(report.longrepr),
                "description": None,
            }

    def _format_test_name(self, report):
        parts = report.nodeid.split("::")
        return f"[{parts[0]}] {'.'.join(parts[1:])}" if len(parts) > 1 else f"[{parts[0]}]"


class PyTest(Test):
    def __init__(
        self,
        tester: "PyTester",
        test_file: str,
        result: Dict,
    ):
        """
        Initialize a Python test created by tester.

        The result was created after running some unittest or pytest tests.
        """
        self._test_name = result["name"]
        self._file_name = test_file
        self.description = result.get("description")
        self.status = result["status"]
        self.message = result["errors"]
        super().__init__(tester)

        # Override self.points_total attribute (set in Test initializer)
        if "marks_total" in result:
            self.points_total = result["marks_total"]

        self.points_earned = result.get("marks_earned")

    @property
    def test_name(self) -> str:
        """The name of this test"""
        if self.description:
            return f"{self._test_name} ({self.description})"
        return self._test_name

    @Test.run_decorator
    def run(self) -> str:
        """
        Return a json string containing all test result information.
        """
        if self.points_earned is not None and 0 < self.points_earned < self.points_total:
            return self.partially_passed(points_earned=self.points_earned, message=self.message)
        elif self.points_earned is not None and self.points_earned > self.points_total:
            bonus = self.points_earned - self.points_total
            return self.passed_with_bonus(points_bonus=bonus, message=self.message)
        elif self.status == "success":
            return self.passed(message=self.message)
        elif self.status == "failure":
            return self.failed(message=self.message)
        else:
            return self.error(message=self.message)


class PyTester(Tester):
    def __init__(
        self,
        specs: TestSpecs,
        test_class: Type[PyTest] = PyTest,
        resource_settings: list[tuple[int, tuple[int, int]]] | None = None,
    ):
        """
        Initialize a python tester using the specifications in specs.

        This tester will create tests of type test_class.
        """
        super().__init__(specs, test_class, resource_settings=resource_settings)
        self.annotations = []
        self.extra_marks = []
        self.overall_comments = []
        self.tags = set()

    @staticmethod
    def _load_unittest_tests(test_file: str) -> unittest.TestSuite:
        """
        Discover unittest tests in test_file and return
        a unittest.TestSuite that contains these tests
        """
        test_loader = unittest.defaultTestLoader
        test_file_dir = os.path.dirname(test_file)
        discovered_tests = test_loader.discover(test_file_dir, test_file)
        return unittest.TestSuite(discovered_tests)

    def _run_unittest_tests(self, test_file: str) -> List[Dict]:
        """
        Run unittest tests in test_file and return the results
        of these tests
        """
        test_suite = self._load_unittest_tests(test_file)
        with open(os.devnull, "w") as nullstream:
            test_runner = unittest.TextTestRunner(
                verbosity=self.specs["test_data", "output_verbosity"],
                stream=nullstream,
                resultclass=TextTestResults,
            )
            test_result = test_runner.run(test_suite)
        return test_result.results

    def _run_pytest_tests(self, test_file: str) -> List[Dict]:
        """
        Run unittest tests in test_file and return the results
        of these tests
        """
        results = []
        with open(os.devnull, "w") as null_out:
            try:
                sys.stdout = null_out
                verbosity = self.specs["test_data", "output_verbosity"]
                plugin = PytestPlugin()
                pytest.main([test_file, f"--tb={verbosity}"], plugins=[plugin])
                results.extend(plugin.results.values())
                self.annotations = plugin.annotations
                self.overall_comments = plugin.overall_comments
                self.extra_marks = plugin.extra_marks
                self.tags = plugin.tags
            finally:
                sys.stdout = sys.__stdout__
        return results

    def run_python_tests(self) -> Dict[str, List[Dict]]:
        """
        Return a dict mapping each filename to its results
        """
        results = {}
        for test_file in self.specs["test_data", "script_files"]:
            if self.specs["test_data", "tester"] == "unittest":
                result = self._run_unittest_tests(test_file)
            else:
                result = self._run_pytest_tests(test_file)
            results[test_file] = result
        return results

    @Tester.run_decorator
    def run(self) -> None:
        """
        Runs all tests in this tester.
        """
        results = self.run_python_tests()
        for test_file, result in results.items():
            for res in result:
                test = self.test_class(self, test_file, res)
                print(test.run(), flush=True)

    def after_tester_run(self) -> None:
        """Print all MarkUs metadata from the tests."""
        if self.annotations:
            print(self.test_class.format_annotations(self.annotations))
        if self.tags:
            print(self.test_class.format_tags(self.tags))
        if self.overall_comments:
            print(self.test_class.format_overall_comment(self.overall_comments, separator="\n\n"))
        if self.extra_marks:
            print(self.test_class.format_extra_marks(self.extra_marks))
