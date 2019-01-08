#!/usr/bin/env python3

from markus_sql_tester import MarkusSQLTester
from markus_tester import MarkusTestSpecs

if __name__ == '__main__':

    SPECS = MarkusTestSpecs()

    # Students are required to create a solution table in their submission, named as the sql file without the file
    # extension; e.g. an 'example.sql' file must have a 'CREATE TABLE example [...];' in it.
    # Students are also required to submit an additional sql file with '_order' suffix for each submission that cares
    # about ordering, which selects from their solution table and does the ordering; e.g. an 'example.sql' file must
    # have an additional 'example_order.sql' file with a 'SELECT * FROM example ORDER BY [...];' in it)

    # The points assigned to each test case; points can be assigned in three ways:
    # 1) to some tests+datasets
    #    SPECS['points'] = {'test1': {'data1': 11, 'data2': 12}, 'test2': {'data1': 21, 'data2': 22}}
    # 2) to all datasets of some tests
    #    SPECS['test_points'] = {'test1': 1, 'test2': 2}
    # 3) to all tests of some datasets
    #    SPECS['data_points'] = {'data1': 1, 'data2': 2}
    # If you don't specify some tests/datasets from the solution, they are assigned a default of 1 point.
    SPECS['data_points'] = {'data1.sql': 1, 'data2.sql': 2}

    # The schema name (defaults to no schema if commented out).
    SPECS['schema_name'] = 'autotest'

    # The feedback file name (defaults to no feedback file if commented out).
    # SPECS['feedback_file'] = 'feedback_sql.txt'

    tester = MarkusSQLTester(specs=SPECS)
    tester.run()
