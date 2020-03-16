import json
import subprocess
import os
from typing import Dict, Optional, IO, Type

from testers.markus_tester import MarkusTester, MarkusTest, MarkusTestError


class MarkusRacketTest(MarkusTest):
    def __init__(
        self,
        tester: "MarkusRacketTester",
        result: Dict,
        feedback_open: Optional[IO] = None,
    ) -> None:
        """
        Initialize a racket test created by tester.

        The result was created after running the tests in test_file and test feedback
        will be written to feedback_open.
        """
        self._test_name = result["name"]
        self.status = result["status"]
        self.message = result["message"]
        super().__init__(tester, feedback_open)

    @property
    def test_name(self) -> None:
        """ The name of this test """
        return self._test_name

    @MarkusTest.run_decorator
    def run(self) -> str:
        """
        Return a json string containing all test result information.
        """
        if self.status == "pass":
            return self.passed()
        elif self.status == "fail":
            return self.failed(message=self.message)
        else:
            return self.error(message=self.message)


class MarkusRacketTester(MarkusTester):

    ERROR_MSGS = {"bad_json": "Unable to parse test results: {}"}

    def __init__(
        self, specs, test_class: Type[MarkusRacketTest] = MarkusRacketTest
    ) -> None:
        """
        Initialize a racket tester using the specifications in specs.

        This tester will create tests of type test_class.
        """
        super().__init__(specs, test_class)

    def run_racket_test(self) -> Dict[str, str]:
        """
        Return the stdout captured from running each test script file with markus.rkt tester.
        """
        results = {}
        markus_rkt = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "lib", "markus.rkt"
        )
        for group in self.specs["test_data", "script_files"]:
            test_file = group.get("script_file")
            if test_file:
                suite_name = group.get("test_suite_name", "all-tests")
                cmd = [markus_rkt, "--test-suite", suite_name, test_file]
                rkt = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    check=True,
                )
                results[test_file] = rkt.stdout
        return results

    @MarkusTester.run_decorator
    def run(self) -> None:
        """
        Runs all tests in this tester.
        """
        try:
            results = self.run_racket_test()
        except subprocess.CalledProcessError as e:
            raise MarkusTestError(e.stderr) from e
        with self.open_feedback() as feedback_open:
            for test_file, result in results.items():
                if result.strip():
                    try:
                        test_results = json.loads(result)
                    except json.JSONDecodeError as e:
                        msg = MarkusRacketTester.ERROR_MSGS["bad_json"].format(result)
                        raise MarkusTestError(msg) from e
                    for t_result in test_results:
                        test = self.test_class(self, feedback_open, t_result)
                        print(test.run(), flush=True)
