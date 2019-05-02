import json
import subprocess
import os

from testers.markus_tester import MarkusTester, MarkusTest


class MarkusRacketTest(MarkusTest):

    def __init__(self, tester, feedback_open, result):
        self._test_name = result['name']
        self.status = result['status']
        self.message = result['message']
        super().__init__(tester, feedback_open)

    @property
    def test_name(self):
        return self._test_name

    @MarkusTest.run_decorator
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
        for group in self.specs['test_data', 'script_files']:
            test_file = group.get('script_file')
            if test_file:
                suite_name = group.get('test_suite_name', 'all-tests')
                cmd = [markus_rkt, '--test-suite', suite_name, test_file]
                rkt = subprocess.run(cmd, stdout=subprocess.PIPE, universal_newlines=True)
                results[test_file] = rkt.stdout
        return results
        
    @MarkusTester.run_decorator
    def run(self):
        try:
            results = self.run_racket_test()
        except subprocess.CalledProcessError as e:
            msg = e.stdout + e.stderr
            raise type(e)(msg) from e
        feedback_file = self.specs.get('test_data', 'feedback_file_name')
        with MarkusTester.open_feedback(feedback_file) as feedback_open:
            for test_file, result in results.items():
                if result.strip():
                    try:
                        test_results = json.loads(result)
                    except json.JSONDecodeError as e:
                        msg = MarkusRacketTester.ERROR_MSGS['bad_json'].format(result)
                        raise type(e)(msg) from e
                    for t_result in test_results:
                        test = self.test_class(self, feedback_open, t_result)
                        print(test.run(), flush=True)
