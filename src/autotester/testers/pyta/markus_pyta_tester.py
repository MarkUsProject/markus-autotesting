import os
import sys
import json
from typing import Optional, IO, Type, Dict

import python_ta
from pylint.config import VALIDATORS
from python_ta.reporters import PositionReporter, PlainReporter
from testers.markus_test_specs import MarkusTestSpecs

from testers.markus_tester import MarkusTester, MarkusTest


class MarkusPyTAReporter(PositionReporter):
    def print_messages(self, level="all"):
        """
        Print error and warning messages to a feedback file
        """
        PlainReporter.print_messages(self, level)
        self._sorted_error_messages.clear()
        self._sorted_style_messages.clear()
        super().print_messages(level)

    def output_blob(self) -> None:
        """
        Override this method so that the default json string report
        doesn't get written to stdout.
        """
        pass


class MarkusPyTATest(MarkusTest):

    ERROR_MSGS = {"reported": "{} error(s)"}

    def __init__(
        self, tester: "MarkusPyTATester", student_file_path: str, max_points: int, feedback_open: Optional[IO] = None,
    ) -> None:
        """
        Initialize a Python TA test that checks the student_file_path file,
        removes 1 point per error from a possible max_points total, and
        writes results to feedback_open.
        """
        self.student_file = student_file_path
        super().__init__(tester, feedback_open)
        self.points_total = max_points
        self.annotations = []

    @property
    def test_name(self) -> str:
        """ The name of this test """
        return f"PyTA {self.student_file}"

    def add_annotations(self, reporter: MarkusPyTAReporter) -> None:
        """
        Records annotations from the results extracted from reporter.
        """
        for result in reporter._output["results"]:
            if "filename" not in result:
                continue
            for msg_group in result.get("msg_errors", []) + result.get("msg_styles", []):
                for msg in msg_group["occurrences"]:
                    self.annotations.append(
                        {
                            "annotation_category_name": None,
                            "filename": result["filename"],
                            "content": msg["text"],
                            "line_start": msg["lineno"],
                            "line_end": msg["end_lineno"],
                            "column_start": msg["col_offset"],
                            "column_end": msg["end_col_offset"],
                        }
                    )

    def after_successful_test_run(self) -> None:
        """ Record all the annotations from this test in the tester object """
        self.tester.annotations.extend(self.annotations)

    @MarkusTest.run_decorator
    def run(self) -> str:
        """
        Return a json string containing all test result information.
        """
        try:
            # run PyTA and collect annotations
            sys.stdout = self.feedback_open if self.feedback_open is not None else self.tester.devnull
            sys.stderr = self.tester.devnull
            reporter = python_ta.check_all(self.student_file, config=self.tester.pyta_config)
            if reporter.current_file_linted is None:
                # No files were checked. The mark is set to 0.
                num_messages = 0
                points_earned = 0
            else:
                self.add_annotations(reporter)
                # deduct 1 point per message occurrence (not type)
                num_messages = len(self.annotations)
                points_earned = max(0, self.points_total - num_messages)
            message = self.ERROR_MSGS["reported"].format(num_messages) if num_messages > 0 else ""
            return self.done(points_earned, message)
        except Exception as e:
            self.annotations = []
            return self.error(message=str(e))
        finally:
            sys.stderr = sys.__stderr__
            sys.stdout = sys.__stdout__


class MarkusPyTATester(MarkusTester):
    def __init__(self, specs: MarkusTestSpecs, test_class: Type[MarkusPyTATest] = MarkusPyTATest):
        """
        Initialize a Python TA tester using the specifications in specs.

        This tester will create tests of type test_class.
        """
        super().__init__(specs, test_class)
        self.feedback_file = self.specs.get("test_data", "feedback_file_name")
        self.annotation_file = self.specs.get("test_data", "annotation_file")
        self.pyta_config = self.update_pyta_config()
        self.annotations = []
        self.devnull = open(os.devnull, "w")
        VALIDATORS[MarkusPyTAReporter.__name__] = MarkusPyTAReporter

    def update_pyta_config(self) -> Dict:
        """
        Return a dictionary containing the configuration options for
        this tester.

        This dictionary is updated to set the pyta-reporter option to
        MarkusPyTAReporter and the pyta-output-file to this tester's
        feedback file.
        """
        config_file = self.specs.get("test_data", "config_file_name")
        if config_file:
            with open(config_file) as f:
                config_dict = json.load(f)
        else:
            config_dict = {}

        config_dict["pyta-reporter"] = "MarkusPyTAReporter"
        if self.feedback_file:
            config_dict["pyta-output-file"] = self.feedback_file

        return config_dict

    def after_tester_run(self) -> None:
        """
        Write annotations extracted from the test results to the
        annotation_file.
        """
        if self.annotation_file and self.annotations:
            with open(self.annotation_file, "w") as annotations_open:
                json.dump(self.annotations, annotations_open)
        if self.devnull:
            self.devnull.close()

    @MarkusTester.run_decorator
    def run(self) -> None:
        """
        Runs all tests in this tester.
        """
        with self.open_feedback(self.feedback_file) as feedback_open:
            for test_data in self.specs.get("test_data", "student_files", default=[]):
                student_file_path = test_data["file_path"]
                max_points = test_data.get("max_points", 10)
                test = self.test_class(self, student_file_path, max_points, feedback_open)
                print(test.run())
