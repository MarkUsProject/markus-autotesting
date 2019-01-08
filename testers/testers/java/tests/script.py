#!/usr/bin/env python3

from markus_java_tester import MarkusJavaTester
from markus_tester import MarkusTestSpecs

if __name__ == '__main__':

    SPECS = MarkusTestSpecs()

    """
    The test files to run (uploaded as support files), and the points assigned:
    points can be assigned per test function, or per test class (every test function in the class will be worth those
    points); if a test function/class is missing, it is assigned a default of 1 point (use POINTS = {} for all 1s).
    """
    POINTS1 = {'testPasses': 1, 'testFails': 1}
    POINTS2 = {'Test2': 2}
    SPECS['test_points'] = {'Test1.java': POINTS1}
    SPECS['test_points'] = {'Test2.java': POINTS2}

    """
    The feedback file name; defaults to no feedback file if commented out.
    """
    # SPECS['feedback_file'] = 'feedback_java.txt'

    tester = MarkusJavaTester(specs=SPECS)
    tester.run()
