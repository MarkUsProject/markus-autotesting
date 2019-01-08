#!/usr/bin/env python3

from markus_pyta_tester import MarkusPyTATester
from markus_tester import MarkusTestSpecs

if __name__ == '__main__':

    SPECS = MarkusTestSpecs()

    """
    The student files to analyze with PyTA, and the points assigned; 1 point will be deducted per message occurrence, to
    a minimum of 0.
    """
    SPECS['test_points'] = {'submission.py': 10}

    """
    The PyTA configuration; you can comment this out and use a support file named .pylintrc instead.
    In either case, you should not specify 'pyta-output-file' and 'pyta-reporter'.
    """
    SPECS['pyta_config'] = {}

    """
    The feedback file name; defaults to no feedback file if commented out.
    """
    # SPECS['feedback_file'] = 'feedback_pyta.txt'

    tester = MarkusPyTATester(specs=SPECS)
    tester.run()
