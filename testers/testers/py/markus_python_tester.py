import os
import tempfile
import unittest
import pytest
import sys
import xml.etree.ElementTree as eTree
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


class AddDocstringToJunitXMLPlugin(object):

    def pytest_itemcollected(self, item):
        docstring = item.obj.__doc__ or ''
        item.user_properties.append(("description", docstring))


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
        name = '.'.join([self._file_name, self._test_name])
        if self.description:
            return f'{name} ({self.description})'
        return name

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

    def _parse_junitxml(self, xml_filename):
        """
        Parse pytest results written to the file named
        xml_filename and yield a hash containing result data
        for each testcase so it can be parsed by MarkusPythonTest.run
        """
        tree = eTree.parse(xml_filename)
        root = tree.getroot()
        for testcase in root.iterfind('testcase'):
            result = {}
            classname = testcase.attrib['classname']    
            testname = testcase.attrib['name']
            result['name'] = '{}.{}'.format(classname, testname)
            failure = testcase.find('failure')
            if failure is not None:
                result['status'] = 'failure'
                result['errors'] = failure.text
            else:
                result['status'] = 'success'
                result['errors'] = ''
            error = testcase.find('error')
            if error is not None:
                result['status'] = 'error'
                result['errors'] = error.text
            description = testcase.find("./properties/property[@name='description']")
            if description is not None:
                result['description'] = description.attrib['value']
            yield result

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
                with tempfile.NamedTemporaryFile(mode="w+", dir=this_dir) as sf:
                    pytest.main([test_file, f'--junitxml={sf.name}', f'--tb={verbosity}'],
                                plugins=[AddDocstringToJunitXMLPlugin()])
                    results = list(self._parse_junitxml(sf))
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
