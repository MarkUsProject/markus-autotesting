import json
import subprocess
import os
from typing import Dict, Type
from ..tester import Tester, Test, TestError


class RacketTest(Test):
    def __init__(self, tester: "RacketTester", result: Dict) -> None:
        """
        Initialize a racket test created by tester.

        The result was created after running the tests in test_file.
        """
        self._test_name = result["name"]
        self.status = result["status"]
        self.message = result["message"]
        super().__init__(tester)

    @property
    def test_name(self) -> None:
        """The name of this test"""
        return self._test_name

    @Test.run_decorator
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


class RacketTester(Tester):
    ERROR_MSGS = {"bad_json": "Unable to parse test results: {}"}

    def __init__(
        self,
        specs,
        test_class: Type[RacketTest] = RacketTest,
        resource_settings: list[tuple[int, tuple[int, int]]] | None = None,
    ) -> None:
        """
        Initialize a racket tester using the specifications in specs.

        This tester will create tests of type test_class.
        """
        super().__init__(specs, test_class, resource_settings=resource_settings)

    def run_racket_test(self) -> Dict[str, str]:
        """
        Return the stdout captured from running each test script file with autotester.rkt tester.
        """
        results = {}
        autotester_rkt = os.path.join(os.path.dirname(os.path.realpath(__file__)), "lib", "autotester.rkt")
        for group in self.specs["test_data", "script_files"]:
            test_file = group.get("script_file")
            if test_file:
                suite_name = group.get("test_suite_name", "all-tests")
                cmd = [autotester_rkt, "--test-suite", suite_name, test_file]
                rkt = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    check=True,
                )
                results[test_file] = rkt.stdout
        return results

    @Tester.run_decorator
    def run(self) -> None:
        """
        Runs all tests in this tester.
        """
        try:
            results = self.run_racket_test()
        except subprocess.CalledProcessError as e:
            raise TestError(e.stderr) from e
        for test_file, result in results.items():
            if result.strip():
                try:
                    test_results = json.loads(result)
                except json.JSONDecodeError as e:
                    msg = RacketTester.ERROR_MSGS["bad_json"].format(result)
                    raise TestError(msg) from e
                for t_result in test_results:
                    test = self.test_class(self, t_result)
                    print(test.run(), flush=True)
