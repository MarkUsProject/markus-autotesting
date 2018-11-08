#!/usr/bin/env python3

from markus_racket_tester import MarkusRacketTester
from markus_tester import MarkusTestSpecs

if __name__ == '__main__':

    SPECS = MarkusTestSpecs()

    '''
    The test files to run (uploaded as support files), and the points assigned:
    points can be assigned per test.  If a test is missing, it is assigned a 
    default of 1 point (use POINTS = {} for all 1s).
    '''
    POINTS = {}
    SPECS['test_points'] = {'test.rkt': POINTS}

    '''
    The name of the test-suite defined in your test files (defaults to 'all-tests' seconds if commented out)
    ex: 
          (define all-tests (test-suite ...) )
    This can either be a string indicating the test-suite name for all test files (defined in SPECS['test_points'])
    or a dictionary mapping each test file name to different test-suite names (not recommended)
    ex:
          SPECS['test_suite_name'] = {'test.rkt': 'all-tests', 'test2.rkt': 'other-tests'}
    '''
    # SPECS['test_suite_name'] = 'all-tests'

    '''
    The feedback file name (defaults to no feedback file if commented out).
    '''
    # SPECS['feedback_file'] = 'feedback_racket.txt'

    tester = MarkusRacketTester(specs=SPECS)
    tester.run()
