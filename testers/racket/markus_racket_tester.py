import contextlib
import enum
import json
import subprocess
import os

from testers.markus_tester import MarkusTester, MarkusTest, MarkusTestSpecs


class MarkusRacketTest(MarkusTest):

    def __init__(self, tester, feedback_open, test_file, result):
        self._test_name = result['name']
        all_points = tester.specs.matrix[test_file][MarkusTestSpecs.MATRIX_NODATA_KEY]
        points = all_points.get(self._test_name, 1)
        self.status = result['status']
        self.message = self.format_message(result)
        super().__init__(tester, test_file, [MarkusTestSpecs.MATRIX_NODATA_KEY], points, {}, feedback_open)

    @property
    def test_name(self):
        return self._test_name

    def format_message(self, result):
        return result['message']

    def run(self):
        if self.status == "pass":
            return self.passed()
        elif self.status == "fail":
            return self.failed(message=self.message)
        else:
            return self.error(message=self.message)


class MarkusRacketTester(MarkusTester):

    ERROR_MSGS = {'bad_json': 'Unable to parse test results: {}'}

    def __init__(self, specs, test_class=MarkusRacketTest):
        super().__init__(specs, test_class)
    
    def run_racket_test(self):
        """
        Return the subprocess.CompletedProcess object for each test file run using the
        markus.rkt tester.  
        """
        results = {}
        markus_rkt = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'lib', 'markus.rkt')
        for test_file in self.specs.tests:
            suite_name = self.specs['test_suite_name'][test_file]
            cmd = [markus_rkt, '--test-suite', suite_name, test_file]
            rkt = subprocess.run(cmd, stdout=subprocess.PIPE, universal_newlines=True)
            results[test_file] = rkt.stdout
        return results
        
    def run(self):
        try:
            try:
                results = self.run_racket_test()
            except subprocess.CalledProcessError as e:
                msg = e.stdout + e.stderr
                print(MarkusTester.error_all(message=msg), flush=True)
                return
            with contextlib.ExitStack() as stack:
                feedback_open = (stack.enter_context(open(self.specs.feedback_file, 'w'))
                                 if self.specs.feedback_file is not None
                                 else None)
                for test_file, result in results.items():
                    if result.strip():
                        try:
                            test_results = json.loads(result)
                        except json.JSONDecodeError:
                            msg = MarkusRacketTester.ERROR_MSGS['bad_json'].format(result)
                            print(MarkusTester.error_all(message=msg), flush=True)
                            continue
                        for t_result in test_results:
                            test = self.test_class(self, feedback_open, test_file, t_result)
                            print(test.run(), flush=True)
        except Exception as e:
            print(MarkusTester.error_all(message=str(e)), flush=True)
            return
