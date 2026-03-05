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
        return self.test_name_

    @Test.run_decorator
    def run(self):
        if self.status == "passed":
            return self.passed()
        else:
            return self.failed(self.message)


class JsTester(Tester):

    def __init__(
        self,
        specs: TestSpecs,
        test_class=JsTest,
        resource_settings: list[tuple[int, tuple[int, int]]] | None = None,
    ) -> None:
        super().__init__(specs, test_class, resource_settings=resource_settings)

    def _run_npm_install(self, dir_path):
        result = subprocess.run(
            ["npm", "install"],
            capture_output=True,
            text=True,
            cwd=dir_path,
        )
        return result

    def _run_jest(self, dir_path, test_files=None):
        # `--json` -> output JSON to stdout
        # `--forceExit` -> prevents jest from hanging if tests open connections
        cmd = ["npx", "jest", "--json", "--forceExit"]
        if test_files:
            cmd.extend(test_files)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=dir_path,
        )
        return result.stdout, result.returncode

    def _parse_jest_output(self, raw_json):
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            return None, e

        results = []
        for test_suite in data.get("testResults", []):
            for test in test_suite.get("testResults", []):
                results.append(test)

        return results, None

    @Tester.run_decorator
    def run(self):
        dir_path = os.getcwd()

        npm_result = self._run_npm_install(dir_path)
        if npm_result.returncode != 0:
            raise TestError(f"npm install failed:\n{npm_result.stderr}")

        script_files = self.specs.get("test_data", "script_files", default=[])
        jest_json_output, _ = self._run_jest(dir_path, test_files=script_files)

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
