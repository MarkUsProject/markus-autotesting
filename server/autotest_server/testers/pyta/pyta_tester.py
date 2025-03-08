import os
import sys
import io
import json
from typing import Type, Dict, List

import python_ta
from ..tester import Tester, Test
from ..specs import TestSpecs


class PytaReporter(python_ta.reporters.json_reporter.JSONReporter, python_ta.reporters.plain_reporter.PlainReporter):
    pass


class PytaTest(Test):
    ERROR_MSGS = {"reported": "{} error(s)"}

    def __init__(
        self,
        tester: "PytaTester",
        student_file_path: str,
        max_points: int,
    ) -> None:
        """
        Initialize a Python TA test that checks the student_file_path file,
        removes 1 point per error from a possible max_points total.
        """
        self.student_file = student_file_path
        super().__init__(tester)
        self.points_total = max_points
        self.annotations = []

    @property
    def test_name(self) -> str:
        """The name of this test"""
        return f"Pyta {self.student_file}"

    def add_annotations(self, data: List[Dict]) -> None:
        """
        Records annotations from the results extracted from reporter.
        """
        for result in data:
            if result.get("filename") == self.student_file:
                for msg in result["msgs"]:
                    self.annotations.append(
                        {
                            "filename": result["filename"],
                            "content": msg["msg"],
                            "line_start": msg["line"],
                            "line_end": msg["end_line"],
                            "column_start": msg["column"],
                            "column_end": msg["end_column"],
                        }
                    )

    def after_successful_test_run(self) -> None:
        """Record all the annotations from this test in the tester object"""
        self.tester.annotations.extend(self.annotations)

    @Test.run_decorator
    def run(self) -> str:
        """
        Return a json string containing all test result information.
        """
        if not os.path.exists(self.student_file):
            return self.error(message=f"File does not exist: {self.student_file}")
        tmp_stderr = io.StringIO()
        try:
            sys.stderr = tmp_stderr
            with open(os.devnull, "w") as devnull:
                sys.stdout = devnull
                reporter = python_ta.check_all(self.student_file, config=self.tester.pyta_config)
            tmp_stdout = io.StringIO()
            reporter.out = tmp_stdout
            reporter.display_messages(None)

            report_stdout = io.StringIO()
            reporter.out = report_stdout
            reporter.print_messages()
        finally:
            sys.stderr = sys.__stderr__
            sys.stdout = sys.__stdout__
        tmp_stdout.seek(0)
        report_stdout.seek(0)
        try:
            data = json.load(tmp_stdout)
        except json.JSONDecodeError:
            tmp_stderr.seek(0)
            tmp_stdout.seek(0)
            self.annotations = []
            return self.error(message=f"{tmp_stderr.read()}\n\n{tmp_stdout.read()}")

        self.add_annotations(data)
        num_messages = len(self.annotations)
        points_earned = max(0, self.points_total - num_messages)

        message = report_stdout.read()
        return self.done(points_earned, message)


class PytaTester(Tester):
    test_class: Type[PytaTest]

    def __init__(
        self,
        specs: TestSpecs,
        test_class: Type[PytaTest] = PytaTest,
        resource_settings: list[tuple[int, tuple[int, int]]] | None = None,
    ):
        """
        Initialize a Python TA tester using the specifications in specs.

        This tester will create tests of type test_class.
        """
        super().__init__(specs, test_class, resource_settings=resource_settings)
        self.upload_annotations = self.specs.get("test_data", "upload_annotations")
        self.pyta_config = self.update_pyta_config()
        self.annotations = []

    def update_pyta_config(self) -> Dict:
        """
        Return a dictionary containing the configuration options for
        this tester.

        This dictionary is updated to set the pyta-reporter option to
        PytaReporter and the pyta-output-file to this tester's
        feedback file.
        """
        config_file = self.specs.get("test_data", "config_file_name")
        if config_file:
            with open(config_file) as f:
                config_dict = json.load(f)
        else:
            config_dict = {}

        config_dict["output-format"] = "testers.pyta.pyta_tester.PytaReporter"

        return config_dict

    def after_tester_run(self) -> None:
        """
        Write annotations extracted from the test results to stdout.
        """
        if self.upload_annotations:
            print(self.test_class.format_annotations(self.annotations))

    @Tester.run_decorator
    def run(self) -> None:
        """
        Runs all tests in this tester.
        """
        for test_data in self.specs.get("test_data", "student_files", default=[]):
            student_file_path = test_data["file_path"]
            max_points = test_data.get("max_points", 10)
            test = self.test_class(self, student_file_path, max_points)
            print(test.run())
