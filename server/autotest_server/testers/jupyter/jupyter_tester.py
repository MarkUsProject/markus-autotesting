import os
import sys
import re
from typing import Type, Dict, List, ContextManager
import pytest
import nbformat
import tempfile
from contextlib import contextmanager
from notebook_helper import merger
from .lib.jupyter_pytest_plugin import JupyterPlugin

from ..tester import Tester, Test
from ..specs import TestSpecs


class JupyterTest(Test):
    def __init__(
        self,
        tester: "JupyterTester",
        test_file: str,
        test_file_name: str,
        result: Dict,
    ):
        """
        Initialize a Jupyter test created by tester.

        The result was created after running some pytest tests.
        """
        self._test_name = re.sub(r"^.*?(?=::)", test_file_name, result["name"])
        self._file_name = test_file
        self.description = result.get("description")
        self.status = result["status"]
        self.message = result["errors"]
        super().__init__(tester)

    @property
    def test_name(self) -> str:
        """The name of this test"""
        if self.description:
            return f"{self._test_name} ({self.description})"
        return self._test_name

    @Test.run_decorator
    def run(self) -> str:
        """
        Return a json string containing all test result information.
        """
        if self.status == "success":
            return self.passed(message=self.message)
        elif self.status == "failure":
            return self.failed(message=self.message)
        else:
            return self.error(message=self.message)


class JupyterTester(Tester):
    def __init__(
        self,
        specs: TestSpecs,
        test_class: Type[JupyterTest] = JupyterTest,
        resource_settings: list[tuple[int, tuple[int, int]]] | None = None,
    ):
        """
        Initialize a jupyter tester using the specifications in specs.

        This tester will create tests of type test_class.
        """
        super().__init__(specs, test_class, resource_settings=resource_settings)

    @staticmethod
    def _run_jupyter_tests(test_file: str) -> List[Dict]:
        results = []
        with open(os.devnull, "w") as null_out:
            try:
                sys.stdout = null_out
                plugin = JupyterPlugin()
                pytest.main([test_file], plugins=["notebook_helper.pytest.notebook_collector_plugin", plugin])
                results.extend(plugin.results.values())
            finally:
                sys.stdout = sys.__stdout__
        return results

    @contextmanager
    def _merge_ipynb_files(self, test_file: str, submission_file: str) -> ContextManager[str]:
        tempf = tempfile.NamedTemporaryFile(dir=os.getcwd(), mode="w", delete=False, suffix=".ipynb")
        new_notebook = merger.merge(test_file, submission_file)
        try:
            nbformat.write(new_notebook, tempf)
            tempf.close()
            yield tempf.name
        finally:
            os.unlink(tempf.name)

    def test_merge(self, test_file: str, submission_file: str, make_test: bool = False) -> None:
        error = None
        try:
            merger.check(test_file, submission_file)
        except Exception as e:
            error = str(e)
        if make_test:
            if error is None:
                result = {"status": "success", "name": "merge_check", "errors": ""}
            else:
                result = {"status": "failure", "name": "merge_check", "errors": error}
            test = self.test_class(self, test_file, f"{test_file}:{submission_file}", result)
            print(test.run(), flush=True)
        elif error:
            sys.stderr.write(error)
            sys.stderr.flush()

    @Tester.run_decorator
    def run(self) -> None:
        """
        Runs all tests in this tester.
        """
        for script_files in self.specs["test_data", "script_files"]:
            test_file = script_files["test_file"]
            submission_file = script_files["student_file"]
            self.test_merge(test_file, submission_file, script_files["test_merge"])
            with self._merge_ipynb_files(test_file, submission_file) as merged_file:
                for res in self._run_jupyter_tests(merged_file):
                    test = self.test_class(self, merged_file, f"{test_file}:{submission_file}", res)
                    print(test.run(), flush=True)
