import contextlib
import subprocess
import os
import tempfile
import csv

from testers.markus_tester import MarkusTester, MarkusTest, MarkusTestSpecs

class MarkusHaskellTest(MarkusTest):

    def __init__(self, tester, feedback_open, test_file, result):
        self._test_name = result['name']
        all_points = tester.specs.matrix[test_file][MarkusTestSpecs.MATRIX_NODATA_KEY]
        points = all_points.get(self._test_name, 1)
        self.status = result['status']
        self.message = result['description']
        super().__init__(tester, test_file, [MarkusTestSpecs.MATRIX_NODATA_KEY], points, {}, feedback_open)

    @property
    def test_name(self):
        return self._test_name

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
        flags = [module_flag, stats_flag]
        flags.append(f"--timeout={self.specs['test_timeout']}s")
        flags.append(f"--quickcheck-tests={self.specs['test_cases']}")
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

    def _get_haskell_env(self):
        """
        Return a dictionary of all environment variables required to run haskell tests.
        The environment variable are a copy of the current environment with extra paths
        added to the GHC_PACKAGE_PATH.

        GHC_PACKAGE_PATH <- tells the haskell compiler where to find installed packages
        """
        ghc_pkg_pth = self.specs.get('ghc_package_path')
        if ghc_pkg_pth is not None:
            return {**os.environ, **{'GHC_PACKAGE_PATH' : ghc_pkg_pth}}
        return os.environ

    def run_haskell_tests(self):
        """
        Return test results for each test file. Results contain a list of parsed test results and the 
        output of stderr from running the tests. 

        Tests are run by first discovering all tests from a specific module (using tasty-discover)
        and then running all the discovered tests and parsing the results from a csv file.
        """
        results = {}
        this_dir = os.getcwd()
        for test_file in self.specs.tests:
            with tempfile.NamedTemporaryFile(dir=this_dir) as f:
                cmd = ['tasty-discover', '.', '_', f.name] + self._test_run_flags(test_file)
                discover_proc = subprocess.run(cmd, stdout=subprocess.DEVNULL,
                                               universal_newlines=True, env=self._get_haskell_env())
                with tempfile.NamedTemporaryFile(mode="w+", dir=this_dir) as sf:
                    cmd = ['runghc', f.name, f"--stats={sf.name}"]
                    test_proc = subprocess.run(cmd, stdout=subprocess.DEVNULL,
                                               universal_newlines=True, env=self._get_haskell_env())
                    results[test_file] = {'stderr':test_proc.stderr, 'results':self._parse_test_results(csv.reader(sf))}
        return results

    def run(self):
        try:
            try:
                results = self.run_haskell_tests()
            except subprocess.CalledProcessError as e:
                msg = (e.stdout or '' + e.stderr or '') or str(e)
                print(MarkusTester.error_all(message=msg), flush=True)
                return
            with contextlib.ExitStack() as stack:
                feedback_open = (stack.enter_context(open(self.specs.feedback_file, 'w'))
                                 if self.specs.feedback_file is not None
                                 else None)
                for test_file, result in results.items():
                    if result['stderr']:
                        print(MarkusTester.error_all(message=result['stderr']), flush=True)
                    for res in result['results']:
                        test = self.test_class(self, feedback_open, test_file, res)
                        print(test.run(), flush=True)
        except Exception as e:
            print(MarkusTester.error_all(message=str(e)), flush=True)
            return
