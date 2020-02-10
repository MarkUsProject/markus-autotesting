import os
import sys
import json
from collections import defaultdict

import python_ta
from pylint.config import VALIDATORS
from python_ta.reporters import PositionReporter, PlainReporter

from testers.markus_tester import MarkusTester, MarkusTest


class MarkusPyTAReporter(PositionReporter):
    def __init__(self, *args, **kwargs):
        super().__init__(self, *args, **kwargs)
        self._sorted_error_messages = defaultdict(list)

    def print_messages(self, level="all"):
        # print to feedback file, then reset and generate data for annotations
        PlainReporter.print_messages(self, level)
        super().print_messages(level)

    def output_blob(self):
        pass


class MarkusPyTATest(MarkusTest):

    ERROR_MSGS = {"reported": "{} error(s)"}

    def __init__(self, tester, student_file_path, max_points, feedback_open=None):
        self.student_file = student_file_path
        super().__init__(tester, feedback_open)
        self.points_total = max_points
        self.annotations = []

    @property
    def test_name(self):
        return f"PyTA {self.student_file}"

    def add_annotations(self, reporter):
        for result in reporter._output["results"]:
            if "filename" not in result:
                continue
            for msg_group in result.get("msg_errors", []) + result.get(
                "msg_styles", []
            ):
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

    def after_successful_test_run(self):
        self.tester.annotations.extend(self.annotations)

    @MarkusTest.run_decorator
    def run(self):
        try:
            # run PyTA and collect annotations
            sys.stdout = (
                self.feedback_open
                if self.feedback_open is not None
                else self.tester.devnull
            )
            sys.stderr = self.tester.devnull
            reporter = python_ta.check_all(
                self.student_file, config=self.tester.pyta_config
            )
            if reporter.current_file_linted is None:
                # No files were checked. The mark is set to 0.
                num_messages = 0
                points_earned = 0
            else:
                self.add_annotations(reporter)
                # deduct 1 point per message occurrence (not type)
                num_messages = len(self.annotations)
                points_earned = max(0, self.points_total - num_messages)
            message = (
                self.ERROR_MSGS["reported"].format(num_messages)
                if num_messages > 0
                else ""
            )
            return self.done(points_earned, message)
        except Exception as e:
            self.annotations = []
            return self.error(message=str(e))
        finally:
            sys.stderr = sys.__stderr__
            sys.stdout = sys.__stdout__


class MarkusPyTATester(MarkusTester):
    def __init__(self, specs, test_class=MarkusPyTATest):
        super().__init__(specs, test_class)
        self.feedback_file = self.specs.get("test_data", "feedback_file_name")
        self.annotation_file = self.specs.get("test_data", "annotation_file")
        self.pyta_config = self.update_pyta_config()
        self.annotations = []
        self.devnull = open(os.devnull, "w")
        VALIDATORS[MarkusPyTAReporter.__name__] = MarkusPyTAReporter

    def update_pyta_config(self):
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

    def after_tester_run(self):
        if self.annotation_file and self.annotations:
            with open(self.annotation_file, "w") as annotations_open:
                json.dump(self.annotations, annotations_open)
        if self.devnull:
            self.devnull.close()

    @MarkusTester.run_decorator
    def run(self):
        with self.open_feedback(self.feedback_file) as feedback_open:
            for test_data in self.specs.get("test_data", "student_files", default=[]):
                student_file_path = test_data["file_path"]
                max_points = test_data.get("max_points", 10)
                test = self.test_class(
                    self, student_file_path, max_points, feedback_open
                )
                print(test.run())
