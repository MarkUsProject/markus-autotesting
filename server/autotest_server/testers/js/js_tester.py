import subprocess
import json
import os

from ..tester import Tester, Test

# Reference: java_tester.py + py_tester.py for the pattern
# general flow: run test runner -> parse output -> print JSON per test

class JsTest(Test):
    # Reference: JavaTest
    # Notes: jest result fieldsm are fullName, status ("passed"/"failed"/"pending"), failureMessages

    def __init__(self, tester, result):
        self.test_name_ = result.get("fullName", "unknown")
        self.status = result.get("status")

        super().__init__(tester)

    @property
    def test_name(self):
        return self.test_name_

    @Test.run_decorator
    def run(self):
        if self.status == "passed":
            return self.passed()
        elif self.status == "failed":
            return self.failed(self.message)
        else:
            # TODO: jest can return "pending" (skipped tests), not sure how to this handle yet
            return self.error("undetermined")


class JsTester(Tester):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # java_tester sets up classpaths + temp dirs here. Not too too sure what we need equivalent of for js yet

    def _run_npm_install(self, dir_path):
        result = subprocess.run(
            ["npm", "install"],
            capture_output=True,
            text=True,
            cwd=dir_path,
        )
        return result

    def _run_jest(self, dir_path):
        # `--json` -> output JSON to stdout
        # `--forceExit` -> "prevents jest from hanging if tests open connections"
        result = subprocess.run(
            ["npx", "jest", "--json", "--forceExit"],
            capture_output=True,
            text=True,
            cwd=dir_path,
        )
        return result.stdout, result.returncode

    def _parse_jest_output(self, raw_json):
        # json struct:
        # {
        #   "testResults": [
        #     {
        #       "testResults": [
        #         {
        #           "fullName": ...,
        #           "status": ...,
        #           "failureMessages": ["..."],
        #           "duration": ...
        #         }
        #       ]
        #     }
        #   ],
        #   "success": ...,
        #   "numPassedTests": ...,
        #   ...
        # }
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            # TODO: error handling for when jest crashes before outputing json
            return None, e

        results = []
        for test_suite in data.get("testResults", []):
            for test in test_suite.get("testResults", []):
                results.append(test)

        return results, None

    @Tester.run_decorator
    def run(self):
        # Need to figure out the spec format yet
        dir_path = os.getcwd()

        # Do `npm install`
        npm_result = self._run_npm_install(dir_path)
        if npm_result.returncode != 0:
            self.error_all(f"Failed to install npm: {npm_result.stderr}")
            return

        # run jest
        jest_json_output, jest_exit_code = self._run_jest(dir_path)

        if not jest_json_output:
            self.error_all("No output produced")
            return

        # parse output
        test_results, err = self._parse_jest_output(jest_json_output)
        if err:
            self.error_all(err)
            return

        # print each test result as JSON just like java_tester
        for result in test_results:
            test = JsTest(self, result)
            print(test.run())
