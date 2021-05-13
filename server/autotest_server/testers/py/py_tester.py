import os
import unittest
from typing import TextIO, Tuple, Optional, Type, Dict, IO, List
from types import TracebackType
import pytest
import sys
from ..tester import Tester, Test
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
        self.results.append({"status": "success", "name": test.id(), "errors": "", "description": test._testMethodDoc})
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
                "name": test.id(),
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
            {"status": "error", "name": test.id(), "errors": self.errors[-1][-1], "description": test._testMethodDoc}
        )


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
        if rep.failed or item.nodeid not in self.results:
            self.results[item.nodeid] = {
                "status": "failure" if rep.failed else "success",
                "name": item.nodeid,
                "errors": str(rep.longrepr) if rep.failed else "",
                "description": item.obj.__doc__,
            }
        return rep

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
                "name": report.nodeid,
                "errors": str(report.longrepr),
                "description": None,
            }


class PyTest(Test):
    def __init__(
        self,
        tester: "PyTester",
        test_file: str,
        result: Dict,
        feedback_open: Optional[IO] = None,
    ):
        """
        Initialize a Python test created by tester.

        The result was created after running some unittest or pytest tests.
        Test feedback will be written to feedback_open.
        """
        self._test_name = result["name"]
        self._file_name = test_file
        self.description = result.get("description")
        self.status = result["status"]
        self.message = result["errors"]
        super().__init__(tester, feedback_open)

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
        if self.status == "success":
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
    ):
        """
        Initialize a python tester using the specifications in specs.

        This tester will create tests of type test_class.
        """
        super().__init__(specs, test_class)

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
        with self.open_feedback() as feedback_open:
            for test_file, result in results.items():
                for res in result:
                    test = self.test_class(self, test_file, res, feedback_open)
                    print(test.run(), flush=True)
