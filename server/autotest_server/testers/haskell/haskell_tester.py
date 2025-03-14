import subprocess
import os
import tempfile
import csv
from typing import Dict, Type, List, Iterator, Union

from ..tester import Tester, Test, TestError
from ..specs import TestSpecs


class HaskellTest(Test):
    def __init__(
        self,
        tester: "HaskellTester",
        test_file: str,
        result: Dict,
    ) -> None:
        """
        Initialize a Haskell test created by tester.

        The result was created after running the tests in test_file.
        """
        self._test_name = result.get("name")
        self._file_name = test_file
        self.status = result["status"]
        self.message = result["description"]
        super().__init__(tester)

    @property
    def test_name(self) -> str:
        """The name of this test"""
        if self._test_name:
            return ".".join([self._file_name, self._test_name])
        return self._file_name

    @Test.run_decorator
    def run(self) -> str:
        """
        Return a json string containing all test result information.
        """
        if self.status == "OK":
            return self.passed(message=self.message)
        elif self.status == "FAIL":
            return self.failed(message=self.message)
        else:
            return self.error(message=self.message)


class HaskellTester(Tester):
    TASTYSTATS = {"name": 1, "time": 2, "result": 3, "description": -1}

    def __init__(
        self,
        specs: TestSpecs,
        test_class: Type[HaskellTest] = HaskellTest,
        resource_settings: list[tuple[int, tuple[int, int]]] | None = None,
    ) -> None:
        """
        Initialize a Haskell tester using the specifications in specs.

        This tester will create tests of type test_class.
        """
        super().__init__(specs, test_class, resource_settings=resource_settings)

    def _test_run_flags(self, test_file: str) -> List[str]:
        """
        Return a list of additional arguments to the tasty-discover executable
        """
        module_flag = f"--modules={os.path.basename(test_file)}"
        stats_flag = "--ingredient=Stats.consoleStatsReporter"
        flags = [
            module_flag,
            stats_flag,
            f"--timeout={self.specs['test_data', 'test_timeout']}s",
            f"--quickcheck-tests={self.specs['test_data', 'test_cases']}",
        ]
        return flags

    def _parse_test_results(self, reader: Iterator) -> List[Dict[str, Union[int, str]]]:
        """
        Return a list of test result dictionaries parsed from an open
        csv reader object. The reader should be reading a csv file which
        is the output of running a tasty test using the tasty-stats package.
        """
        test_results = []
        for line in reader:
            result = {
                "status": line[self.TASTYSTATS["result"]],
                "name": line[self.TASTYSTATS["name"]],
                "description": line[self.TASTYSTATS["description"]],
                "time": line[self.TASTYSTATS["time"]],
            }
            test_results.append(result)
        return test_results

    def run_haskell_tests(self) -> Dict[str, List[Dict[str, Union[int, str]]]]:
        """
        Return test results for each test file. Results contain a list of parsed test results.

        Tests are run by first discovering all tests from a specific module (using tasty-discover)
        and then running all the discovered tests and parsing the results from a csv file.
        """
        resolver = self.specs["env_data", "resolver_version"]
        STACK_OPTIONS = [f"--resolver={resolver}", "--system-ghc", "--allow-different-user"]
        results = {}
        this_dir = os.getcwd()
        haskell_lib = os.path.join(os.path.dirname(os.path.realpath(__file__)), "lib")
        for test_file in self.specs["test_data", "script_files"]:
            with tempfile.NamedTemporaryFile(dir=this_dir) as f:
                cmd = [
                    "stack",
                    "exec",
                    *STACK_OPTIONS,
                    "--",
                    "tasty-discover",
                    ".",
                    "_",
                    f.name,
                    *self._test_run_flags(test_file),
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, universal_newlines=True, check=True)
                with tempfile.NamedTemporaryFile(mode="w+", dir=this_dir) as sf:
                    cmd = ["stack", "runghc", *STACK_OPTIONS, "--", f"-i={haskell_lib}", f.name, f"--stats={sf.name}"]
                    out = subprocess.run(
                        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, universal_newlines=True, check=False
                    )
                    r = self._parse_test_results(csv.reader(sf))
                    if r:
                        results[test_file] = r
                    else:
                        raise Exception(out.stderr)
        return results

    @Tester.run_decorator
    def run(self) -> None:
        """
        Runs all tests in this tester.
        """
        try:
            results = self.run_haskell_tests()
        except subprocess.CalledProcessError as e:
            raise TestError(e.stderr) from e
        for test_file, result in results.items():
            for res in result:
                test = self.test_class(self, test_file, res)
                print(test.run(), flush=True)
