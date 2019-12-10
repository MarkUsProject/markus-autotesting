import subprocess
import os
import tempfile
import csv

from testers.markus_tester import MarkusTester, MarkusTest, MarkusTestError

class MarkusHaskellTest(MarkusTest):

    def __init__(self, tester, test_file, result, feedback_open=None):
        self._test_name = result.get('name')
        self._file_name = test_file
        self.status = result['status']
        self.message = result['description']
        super().__init__(tester, feedback_open)

    @property
    def test_name(self):
        if self._test_name:
            return '.'.join([self._file_name, self._test_name])
        return self._file_name

    @MarkusTest.run_decorator
    def run(self):
        if self.status == "OK":
            return self.passed(message=self.message)
        elif self.status == "FAIL":
            return self.failed(message=self.message)
        else:
            return self.error(message=self.message)

class MarkusHaskellTester(MarkusTester):

    # column indexes of relevant data from tasty-stats csv
    # reference: http://hackage.haskell.org/package/tasty-stats
    TASTYSTATS = {'name' : 1,
                  'time' : 2,
                  'result' : 3,
                  'description' : -1}

    def __init__(self, specs, test_class=MarkusHaskellTest):
        super().__init__(specs, test_class)
    
    def _test_run_flags(self, test_file):
        """
        Return a list of additional arguments to the tasty-discover executable
        """
        module_flag = f"--modules={os.path.basename(test_file)}"
        stats_flag = "--ingredient=Test.Tasty.Stats.consoleStatsReporter"
        flags = [module_flag,
                 stats_flag,
                 f"--timeout={self.specs['test_data', 'test_timeout']}s",
                 f"--quickcheck-tests={self.specs['test_data', 'test_cases']}"]
        return flags

    def _parse_test_results(self, reader):
        """
        Return a list of test result dictionaries parsed from an open
        csv reader object. The reader should be reading a csv file which
        is the output of running a tasty test using the tasty-stats package.
        """
        test_results = []
        for line in reader:
            result = {'status' : line[self.TASTYSTATS['result']], 
                      'name' : line[self.TASTYSTATS['name']], 
                      'description' : line[self.TASTYSTATS['description']], 
                      'time' : line[self.TASTYSTATS['time']]}
            test_results.append(result)
        return test_results

    def run_haskell_tests(self):
        """
        Return test results for each test file. Results contain a list of parsed test results.

        Tests are run by first discovering all tests from a specific module (using tasty-discover)
        and then running all the discovered tests and parsing the results from a csv file.
        """
        results = {}
        this_dir = os.getcwd()
        for test_file in self.specs['test_data', 'script_files']:
            with tempfile.NamedTemporaryFile(dir=this_dir) as f:
                cmd = ['tasty-discover', '.', '_', f.name] + self._test_run_flags(test_file)
                subprocess.run(cmd, stdout=subprocess.DEVNULL, universal_newlines=True, check=True)
                with tempfile.NamedTemporaryFile(mode="w+", dir=this_dir) as sf:
                    cmd = ['runghc', f.name, f"--stats={sf.name}"]
                    subprocess.run(cmd,
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.PIPE,
                                   universal_newlines=True,
                                   check=True)
                    results[test_file] = self._parse_test_results(csv.reader(sf))
        return results

    @MarkusTester.run_decorator
    def run(self):
        try:
            results = self.run_haskell_tests()
        except subprocess.CalledProcessError as e:
            raise MarkusTestError(e.stderr) from e
        with self.open_feedback() as feedback_open:
            for test_file, result in results.items():
                for res in result:
                    test = self.test_class(self, test_file, res, feedback_open)
                    print(test.run(), flush=True)
