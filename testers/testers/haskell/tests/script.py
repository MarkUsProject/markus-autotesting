#!/usr/bin/env python3

from markus_haskell_tester import MarkusHaskellTester
from markus_tester import MarkusTestSpecs

if __name__ == '__main__':

    SPECS = MarkusTestSpecs()

    '''
    The test files to run (uploaded as support files), and the points assigned:
    points can be assigned per test.  If a test is missing, it is assigned a 
    default of 1 point (use POINTS = {} for all 1s).
    '''
    POINTS = {}
    SPECS['test_points'] = {'Test.hs': POINTS}

    '''
    The max time to run a single test (defaults to 10 seconds if commented out).
    (this timeout may not work in particular cases, e.g. with multi-threading)
    '''
    
    # SPECS['test_timeout'] = 10

    '''
    The number of test cases to run for each quickcheck test 
    (default is 100)
    '''

    # SPECS['test_cases'] = 100

    '''
    The feedback file name (defaults to no feedback file if commented out).
    '''

    # SPECS['feedback_file'] = 'feedback_haskell.txt'

    tester = MarkusHaskellTester(specs=SPECS)
    tester.run()
