#!/usr/bin/env python3

from markus_jdbc_tester import MarkusJDBCTester
from markus_tester import MarkusTestSpecs

if __name__ == '__main__':

    SPECS = MarkusTestSpecs()

    # Students are required to extend JDBCSubmission.java

    # The points assigned to each test case; points can be assigned in three ways:
    # 1) to some tests+datasets
    #    SPECS['points'] = {'test1': {'data1': 11, 'data2': 12}, 'test2': {'data1': 21, 'data2': 22}}
    # 2) to all datasets of some tests
    #    SPECS['test_points'] = {'test1': 1, 'test2': 2}
    # 3) to all tests of some datasets
    #    SPECS['data_points'] = {'data1': 1, 'data2': 2}
    # If you don't specify some tests/datasets from the solution, they are assigned a default of 1 point.
    SPECS['points'] = {'CorrectNoOrder.select':   {'data2j.sql': 2},
                       'CorrectWithOrder.select': {'data2j.sql': 2},
                       'BadSelect.select':        {'data2j.sql': 2},
                       'ExceptionSelect.select':  {'data2j.sql': 2},
                       'CorrectNoOrder.insert':   {'data2j.sql': {'JAVA': 2, 'table1': 2}},
                       'NoInsert.insert':         {'data2j.sql': {'JAVA': 2, 'table1': 2}},
                       'BadInsert.insert':        {'data2j.sql': {'JAVA': 2, 'table1': 2}},
                       'ExceptionInsert.insert':  {'data2j.sql': {'JAVA': 2, 'table1': 2}}}

    # The schema name (defaults to no schema if commented out).
    SPECS['schema_name'] = 'autotest'

    # The feedback file name (defaults to no feedback file if commented out).
    # SPECS['feedback_file'] = 'feedback_jdbc.txt'

    tester = MarkusJDBCTester(specs=SPECS)
    tester.run()
