import subprocess
import os
import json
from typing import Dict, Optional, IO, Type, List, Union

from ..tester import Tester, Test, TestError
from ..specs import TestSpecs


class RTest(Test):
    def __init__(
        self,
        tester: "RTester",
        test_file: str,
        result: Dict,
        feedback_open: Optional[IO] = None,
    ) -> None:
        """
        Initialize a R test created by tester.

        The result was created after running the tests in test_file and test feedback
        will be written to feedback_open.
        """
        self._test_name = f"{test_file}:{result.get('context', '')}:{result['test']}"
        self.result = result["results"]
        super().__init__(tester, feedback_open)
        self.points_total = 0

    @property
    def test_name(self):
        return self._test_name

    @Test.run_decorator
    def run(self):
        messages = []
        successes = 0
        for result in self.result:
            messages.append(result["message"])
            if result["type"] == "expectation_success":
                self.points_total += 1
                successes += 1
            elif result["type"] == "expectation_failure":
                self.points_total += 1

        message = "\n\n".join(messages)
        if successes == self.points_total:
            return self.passed(message=message)
        elif successes > 0:
            return self.partially_passed(points_earned=successes, message=message)
        else:
            return self.failed(message=message)


class RTester(Tester):
    def __init__(
        self,
        specs: TestSpecs,
        test_class: Type[RTest] = RTest,
    ) -> None:
        """
        Initialize a R tester using the specifications in specs.

        This tester will create tests of type test_class.
        """
        super().__init__(specs, test_class)

    def run_r_tests(self) -> Dict[str, List[Dict[str, Union[int, str]]]]:
        """
        Return test results for each test file. Results contain a list of parsed test results.

        Tests are run by first discovering all tests from a specific module (using tasty-discover)
        and then running all the discovered tests and parsing the results from a csv file.
        """
        results = {}
        r_tester = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'lib', 'r_tester.R')
        for test_file in self.specs["test_data", "script_files"]:
            proc = subprocess.run(['Rscript', r_tester, test_file],
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  universal_newlines=True)
            if not results.get(test_file):
                results[test_file] = []
            if proc.returncode == 0:
                results[test_file].extend(json.loads(proc.stdout))
            else:
                raise TestError(proc.stderr)
        return results

    @Tester.run_decorator
    def run(self) -> None:
        """
        Runs all tests in this tester.
        """
        try:
            results = self.run_r_tests()
        except subprocess.CalledProcessError as e:
            raise TestError(e.stderr) from e
        with self.open_feedback() as feedback_open:
            for test_file, result in results.items():
                for res in result:
                    test = self.test_class(self, test_file, res, feedback_open)
                    print(test.run(), flush=True)
