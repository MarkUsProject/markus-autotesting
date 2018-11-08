import os
import sys
import json
from collections import defaultdict

import python_ta
from pylint.config import VALIDATORS
from python_ta.reporters import PositionReporter, PlainReporter

from markus_tester import MarkusTester, MarkusTest


class MarkusPyTAReporter(PositionReporter):

    def print_messages(self, level='all'):
        # print to feedback file, then reset and generate data for annotations
        PlainReporter.print_messages(self, level)
        self._sorted_error_messages = defaultdict(list)
        self._sorted_style_messages = defaultdict(list)
        super().print_messages(level)

    def output_blob(self):
        pass


class MarkusPyTATest(MarkusTest):

    ERROR_MSGS = {
        'reported': "{} error(s)"
    }

    def __init__(self, tester, test_file, data_files, points, test_extra, feedback_open=None):
        super().__init__(tester, test_file, data_files, points, test_extra, feedback_open)
        self.annotations = []

    @property
    def test_name(self):
        return f'PyTA {self.test_file}'

    def add_annotations(self, reporter):
        for result in reporter._output['results']:
            if 'filename' not in result:
                continue
            for msg_group in result.get('msg_errors', []) + result.get('msg_styles', []):
                for msg in msg_group['occurrences']:
                    self.annotations.append({
                        'annotation_category_name': None,
                        'filename': result['filename'],
                        'content': msg['text'],
                        'line_start': msg['lineno'],
                        'line_end': msg['end_lineno'],
                        'column_start': msg['col_offset'],
                        'column_end': msg['end_col_offset']
                    })

    def run(self):
        try:
            # run PyTA and collect annotations
            sys.stdout = self.feedback_open if self.feedback_open is not None else self.tester.devnull
            sys.stderr = self.tester.devnull
            reporter = python_ta.check_all(self.test_file, config=self.tester.pyta_config)
            self.add_annotations(reporter)
            # deduct 1 point per message occurrence (not type)
            num_messages = len(self.annotations)
            points_earned = max(0, self.points_total - num_messages)
            message = self.ERROR_MSGS['reported'].format(num_messages) if num_messages > 0 else ''
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
        self.pyta_config = specs.get('pyta_config', {})
        self.pyta_config['pyta-reporter'] = 'MarkusPyTAReporter'
        if self.specs.feedback_file is not None:
            self.pyta_config['pyta-output-file'] = self.specs.feedback_file
        self.annotations = []
        self.devnull = open(os.devnull, 'w')
        VALIDATORS[MarkusPyTAReporter.__name__] = MarkusPyTAReporter

    def after_successful_test_run(self, test):
        self.annotations.extend(test.annotations)

    def after_tester_run(self):
        if self.specs.feedback_file is not None and self.annotations:
            annotations_file = f'{os.path.splitext(self.specs.feedback_file)[0]}.json'
            with open(annotations_file, 'w') as annotations_open:
                json.dump(self.annotations, annotations_open)
        if self.devnull:
            self.devnull.close()
