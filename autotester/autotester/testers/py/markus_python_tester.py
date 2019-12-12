import os
import tempfile
import unittest
import pytest
import sys
from testers.markus_tester import MarkusTester, MarkusTest


class MarkusTextTestResults(unittest.TextTestResult):
    """
    Custom unittest.TextTestResult that saves results as
    a hash to self.results so they can be more easily
    parsed by the MarkusPythonTest.run function
    """

    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self.results = []
        self.successes = []

    def addSuccess(self, test):
        self.results.append({'status': 'success',
                             'name'  : test.id(),
                             'errors': '',
                             'description': test._testMethodDoc})
        self.successes.append(test)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.results.append({'status': 'failure',
                             'name'  : test.id(),
                             'errors': self.failures[-1][-1],
                             'description': test._testMethodDoc})

    def addError(self, test, err):
        super().addError(test, err)
        self.results.append({'status': 'error',
                             'name'  : test.id(),
                             'errors': self.errors[-1][-1],
                             'description': test._testMethodDoc})


class MarkusPytestPlugin:
    """
    Pytest plugin to collect and parse test results as well
    as any errors during the test collection process.
    """

    def __init__(self):
        self.results = {}

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_runtest_makereport(self, item, call):
        outcome = yield
        rep = outcome.get_result()
        if rep.failed or item.nodeid not in self.results:
            self.results[item.nodeid] = {'status': 'failure' if rep.failed else 'success',
                                         'name': item.nodeid,
                                         'errors': str(rep.longrepr) if rep.failed else '',
                                         'description': item.obj.__doc__}
        return rep

    def pytest_collectreport(self, report):
        if report.failed:
            self.results[report.nodeid] = {'status': 'error',
                                           'name': report.nodeid,
                                           'errors': str(report.longrepr),
                                           'description': None}


class MarkusPythonTest(MarkusTest):

    def __init__(self, tester, test_file, result, feedback_open=None):
        self._test_name = result['name']
        self._file_name = test_file
        self.description = result.get('description')
        self.status = result['status']
        self.message = result['errors']
        super().__init__(tester, feedback_open)

    @property
    def test_name(self):
        if self.description:
            return f'{self._test_name} ({self.description})'
        return self._test_name

    @MarkusTest.run_decorator
    def run(self):
        if self.status == "success":
            return self.passed(message=self.message)
        elif self.status == "failure":
            return self.failed(message=self.message)
        else:
            return self.error(message=self.message)


class MarkusPythonTester(MarkusTester):

    def __init__(self, specs, test_class=MarkusPythonTest):
        super().__init__(specs, test_class)

    def _load_unittest_tests(self, test_file):
        """
        Discover unittest tests in test_file and return
        a unittest.TestSuite that contains these tests
        """
        test_loader = unittest.defaultTestLoader
        test_file_dir = os.path.dirname(test_file)
        discovered_tests = test_loader.discover(test_file_dir, test_file)
        return unittest.TestSuite(discovered_tests)

    def _run_unittest_tests(self, test_file):
        """
        Run unittest tests in test_file and return the results
        of these tests
        """
        test_suite = self._load_unittest_tests(test_file)
        with open(os.devnull, 'w') as nullstream:
            test_runner = unittest.TextTestRunner(
                verbosity=self.specs['test_data', 'output_verbosity'],
                stream=nullstream,
                resultclass=MarkusTextTestResults)
            test_result = test_runner.run(test_suite)
        return test_result.results

    def _run_pytest_tests(self, test_file):
        """
        Run unittest tests in test_file and return the results
        of these tests
        """
        results = []
        this_dir = os.getcwd()
        with open(os.devnull, 'w') as null_out:
            try:
                sys.stdout = null_out
                verbosity = self.specs['test_data', 'output_verbosity']
                plugin = MarkusPytestPlugin()
                pytest.main([test_file, f'--tb={verbosity}'], plugins=[plugin])
                results = list(plugin.results.values())
            finally:
                sys.stdout = sys.__stdout__
        return results

    def run_python_tests(self):
        """
        Return a dict mapping each filename to its results
        """
        results = {}
        for test_file in self.specs['test_data', 'script_files']:
            if self.specs['test_data', 'tester'] == 'unittest':
                result = self._run_unittest_tests(test_file)
            else:
                result = self._run_pytest_tests(test_file)
            results[test_file] = result
        return results

    @MarkusTester.run_decorator
    def run(self):
        results = self.run_python_tests()
        with self.open_feedback() as feedback_open:
            for test_file, result in results.items():
                for res in result:
                    test = self.test_class(self, test_file, res, feedback_open)
                    print(test.run(), flush=True)
