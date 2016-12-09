#!/usr/bin/env python3

import sys
import markus_pam_config as cfg
from markus_pam_tester import MarkusPAMTester
# from markusapi import Markus


if __name__ == '__main__':

    # Modify uppercase variables with your settings
    # The test files (uploaded as support files) to be used for testing the student submission, and the points assigned;
    # the test file names are the keys, the dicts of individual tests (or test classes) and points are the values.
    TEST_POINTS = {'Test1.test_passes': 1, 'Test1.test_fails': 2, 'Test2': 1}
    TEST_SPECS = {'test.py': TEST_POINTS}
    # The max time to run a single test on the student submission.
    TEST_TIMEOUT = 5
    # The max time to run all tests on the student submission.
    GLOBAL_TIMEOUT = 20
    tester = MarkusPAMTester(path_to_uam=cfg.PATH_TO_UAM, specs=TEST_SPECS, test_timeout=TEST_TIMEOUT,
                             global_timeout=GLOBAL_TIMEOUT)
    tester.run()
    # use markus apis if needed (uncomment import markusapi)
    root_url = sys.argv[1]
    api_key = sys.argv[2]
    assignment_id = sys.argv[3]
    group_id = sys.argv[4]
    # file_name = 'result.json'
    # api = Markus(api_key, root_url)
    # with open(file_name) as open_file:
    #     api.upload_feedback_file(assignment_id, group_id, file_name, open_file.read())
