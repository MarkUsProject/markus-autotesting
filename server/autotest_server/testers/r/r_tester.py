import subprocess
import os
import json
from typing import Dict, Type, List, Union

from ..tester import Tester, Test, TestError
from ..specs import TestSpecs


class RTest(Test):
    def __init__(
        self,
        tester: "RTester",
        test_file: str,
        result: Dict,
    ) -> None:
        """
        Initialize a R test created by tester.

        The result was created after running the tests in test_file.
        """
        self._test_name = ":".join(info for info in [test_file, result.get("context"), result["test"]] if info)
        self.result = result["results"]
        super().__init__(tester)
        self.points_total = 0

    @property
    def test_name(self):
        return self._test_name

    @Test.run_decorator
    def run(self):
        messages = []
        successes = 0
        error = False
        for result in self.result:
            # Only add message if not a success, as testthat reports failure messages only
            if result["type"] != "expectation_success":
                messages.append(result["message"])

            if result["type"] == "expectation_success":
                self.points_total += 1
                successes += 1
            elif result["type"] == "expectation_failure":
                self.points_total += 1
            elif result["type"] == "expectation_error":
                error = True
                self.points_total += 1
                messages.append("\n".join(result["trace"]))

        message = "\n\n".join(messages)
        if error:
            return self.error(message=message)
        elif successes == self.points_total:
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
        resource_settings: list[tuple[int, tuple[int, int]]] | None = None,
    ) -> None:
        """
        Initialize a R tester using the specifications in specs.

        This tester will create tests of type test_class.
        """
        super().__init__(specs, test_class, resource_settings=resource_settings)

    def run_r_tests(self) -> Dict[str, List[Dict[str, Union[int, str]]]]:
        """
        Return test results for each test file. Results contain a list of parsed test results.
        """
        results = {}
        r_tester = os.path.join(os.path.dirname(os.path.realpath(__file__)), "lib", "r_tester.R")
        for test_file in self.specs["test_data", "script_files"]:
            proc = subprocess.run(
                ["Rscript", r_tester, test_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                # NO_COLOR is used to ensure R tracebacks are printed without ANSI color codes
                env={**os.environ, "NO_COLOR": "1"},
            )
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
        for test_file, result in results.items():
            for res in result:
                test = self.test_class(self, test_file, res)
                print(test.run(), flush=True)
