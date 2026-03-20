import subprocess
import json
import os

from ..tester import Tester, Test, TestError
from ..specs import TestSpecs


class JsTest(Test):
    def __init__(self, tester, result):
        self.test_name_ = result.get("fullName", "unknown")
        self.status = result.get("status")
        self.message = "\n".join(result.get("failureMessages", []))
        super().__init__(tester)

    @property
    def test_name(self):
        """Return the full name of this test."""
        return self.test_name_

    @Test.run_decorator
    def run(self):
        """Return the result of this test based on its Jest status."""
        if self.status == "passed":
            return self.passed()
        elif self.status == "failed":
            return self.failed(self.message)
        else:
            return self.error(message=self.message or f"Unexpected status: {self.status}")


class JsTester(Tester):

    def __init__(
        self,
        specs: TestSpecs,
        test_class=JsTest,
        resource_settings: list[tuple[int, tuple[int, int]]] | None = None,
    ) -> None:
        """
        Initialize a JavaScript tester using the specifications in specs.

        This tester will create tests of type test_class.
        """
        super().__init__(specs, test_class, resource_settings=resource_settings)

    def _run_pnpm_install(self, dir_path):
        """
        Run pnpm install in dir_path to install dependencies from package.json.
        """
        result = subprocess.run(
            ["pnpm", "install"],
            capture_output=True,
            text=True,
            cwd=dir_path,
        )
        return result

    def _run_jest(self, dir_path, timeout, test_files=None):
        """
        Run Jest in dir_path and return its stdout and return code.

        --json: output results as JSON to stdout
        --forceExit: prevents jest from hanging if tests leave open connections
        --runInBand: run all tests serially in the current process
        """
        local_jest = os.path.join(dir_path, "node_modules", ".bin", "jest")
        jest_cmd = local_jest if os.path.isfile(local_jest) else "jest"
        cmd = [jest_cmd, "--rootDir", dir_path, "--json", "--forceExit", "--runInBand"]
        if test_files:
            cmd.extend(test_files)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=dir_path,
            timeout=timeout,
        )
        return result.stdout, result.returncode

    def _parse_jest_output(self, raw_json):
        """
        Parse Jest's JSON output and return a list of individual test results.

        Returns a tuple (results, error) where error is set if JSON parsing fails.
        """
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            return None, e

        results = []
        for test_suite in data.get("testResults", []):
            for test in test_suite.get("assertionResults", []):
                results.append(test)

        return results, None

    @Tester.run_decorator
    def run(self):
        """
        Run pnpm install and then Jest, parsing the results and printing each test outcome.
        """
        dir_path = os.getcwd()
        test_data = self.specs.get("test_data", default={}) or {}

        timeout = test_data.get("timeout", 30)
        if os.path.isfile(os.path.join(dir_path, "package.json")):
            pnpm_result = self._run_pnpm_install(dir_path)
            if pnpm_result.returncode != 0:
                err = pnpm_result.stderr or pnpm_result.stdout or "(no output)"
                raise TestError(f"pnpm install failed:\n{err}")

        script_files = test_data.get("script_files", [])
        try:
            jest_json_output, jest_rc = self._run_jest(dir_path, timeout, test_files=script_files)
        except subprocess.TimeoutExpired:
            raise TestError("Jest timed out")

        if jest_rc != 0:
            err = jest_json_output
            raise TestError(f"Jest failed (exit code {jest_rc}).\n{err}")
        if not jest_json_output:
            raise TestError("Jest produced no output")

        test_results, err = self._parse_jest_output(jest_json_output)
        if err:
            raise TestError(str(err))

        for result in test_results:
            if result.get("status") == "pending":
                continue
            test = self.test_class(self, result)
            print(test.run(), flush=True)
