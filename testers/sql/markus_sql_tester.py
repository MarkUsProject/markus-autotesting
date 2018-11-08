import getpass
import os
import subprocess

import psycopg2

from markus_tester import MarkusTester, MarkusTest, MarkusTestSpecs


class MarkusSQLTest(MarkusTest):

    ERROR_MSGS = {
        'no_submission': "Submission file '{}' not found",
        'no_submission_order': "Ordering required, order file '{}' not found",
        'bad_col_count': 'Expected {} columns instead of {}',
        'bad_col_name': "Expected column {} to have name '{}' instead of '{}'",
        'bad_col_type': "Expected a different type of values in column '{}' (expected a SQL equivalent of Python type "
                        "'{}' instead of '{}')",
        'bad_col_type_maybe': "Expected a different type of values in column '{}' (but no row values are available to "
                              "check whether they could be compatible types)",
        'bad_row_count': 'Expected {} rows instead of {}',
        'bad_row_content_no_order': 'Expected to find a row {} in the results',
        'bad_row_content_order': 'Expected row {} in the ordered results to be {} instead of {}'
    }
    SCHEMA_FILE = 'schema.ddl'
    DATASET_DIR = 'datasets'

    def __init__(self, tester, test_file, data_files, points, test_extra, feedback_open=None):
        super().__init__(tester, test_file, data_files, points, test_extra, feedback_open)
        self.data_file = data_files[0]

    def select_query(self, schema_name, table_name, order_by=None):
        query = 'SELECT * FROM %(schema)s.%(table)s'
        query_vars = {'schema': psycopg2.extensions.AsIs(schema_name),
                      'table': psycopg2.extensions.AsIs(table_name)}
        if order_by:
            query += ' ORDER BY %(order)s'
            query_vars['order'] = psycopg2.extensions.AsIs(order_by)

        return query, query_vars

    def get_oracle_results(self, table_name, order_by=None):
        query, query_vars = self.select_query(schema_name=self.data_name, table_name=table_name, order_by=order_by)
        self.tester.oracle_cursor.execute(query, query_vars)
        self.tester.oracle_connection.commit()
        oracle_results = self.tester.oracle_cursor.fetchall()

        return oracle_results

    def set_test_schema(self, data_file):
        self.tester.test_cursor.execute('DROP SCHEMA IF EXISTS %(schema)s CASCADE',
                                        {'schema': psycopg2.extensions.AsIs(self.tester.schema_name)})
        self.tester.test_cursor.execute('CREATE SCHEMA %(schema)s',
                                        {'schema': psycopg2.extensions.AsIs(self.tester.schema_name)})
        self.tester.test_cursor.execute('SET search_path TO %(schema)s',
                                        {'schema': psycopg2.extensions.AsIs(self.tester.schema_name)})
        with open(os.path.join(self.tester.path_to_solution, self.SCHEMA_FILE)) as schema_open:
            schema = schema_open.read()
            self.tester.test_cursor.execute(schema)
        if data_file != MarkusTestSpecs.MATRIX_NODATA_KEY:
            with open(os.path.join(self.tester.path_to_solution, self.DATASET_DIR, data_file)) as data_open:
                data = data_open.read()
                self.tester.test_cursor.execute(data)
        self.tester.test_connection.commit()

    def get_test_results(self, table_name, sql_file=None, sql_order_file=None):
        if sql_file is not None:
            with open(sql_file) as sql_open:
                sql = sql_open.read()
                self.tester.test_cursor.execute(sql)
        if sql_order_file is not None:
            with open(sql_order_file) as sql_order_open:
                sql = sql_order_open.read()
                self.tester.test_cursor.execute(sql)
        else:
            query, query_vars = self.select_query(schema_name=self.tester.schema_name, table_name=table_name)
            self.tester.test_cursor.execute(query, query_vars)
        self.tester.test_connection.commit()
        test_results = self.tester.test_cursor.fetchall()

        return test_results

    def check_results(self, oracle_results, test_results, order_on=True):

        oracle_columns = self.tester.oracle_cursor.description
        test_columns = self.tester.test_cursor.description

        # check 1: column count
        oracle_num_columns = len(oracle_columns)
        test_num_columns = len(test_columns)
        if oracle_num_columns != test_num_columns:
            return (MarkusTest.Status.FAIL,
                    self.ERROR_MSGS['bad_col_count'].format(oracle_num_columns, test_num_columns))

        check_column_types = []
        for i, oracle_column in enumerate(oracle_columns):
            # check 2: column names + order
            if test_columns[i].name != oracle_column.name:
                return (MarkusTest.Status.FAIL,
                        self.ERROR_MSGS['bad_col_name'].format(i, oracle_column.name, test_columns[i].name))
            # check 3: column types
            # (strictly different PostgreSQL oid types can be Python-compatible instead, e.g. varchar and text, so this
            # check will be deferred to row analysis)
            if test_columns[i].type_code != oracle_column.type_code:
                if not oracle_results and not test_results:
                    return (MarkusTest.Status.FAIL,
                            self.ERROR_MSGS['bad_col_type_maybe'].format(oracle_column.name))
                if not oracle_results or not test_results:  # will fail on check 4 instead
                    continue
                check_column_types.append(i)

        # check 4: row count
        oracle_num_results = len(oracle_results)
        test_num_results = len(test_results)
        if oracle_num_results != test_num_results:
            return (MarkusTest.Status.FAIL,
                    self.ERROR_MSGS['bad_row_count'].format(oracle_num_results, test_num_results))

        for i, oracle_row in enumerate(oracle_results):
            if order_on:
                test_row = test_results[i]
            else:
                # check 5, unordered variant: row contents
                try:
                    t = test_results.index(oracle_row)
                    test_row = test_results.pop(t)
                except ValueError:
                    return (MarkusTest.Status.FAIL,
                            self.ERROR_MSGS['bad_row_content_no_order'].format(oracle_row))
            checked_column_types = []
            for j in check_column_types:
                # check 3: column types compatibility deferred trigger
                oracle_value = oracle_row[j]
                test_value = test_row[j]
                if test_value is None or oracle_value is None:  # try next row for types
                    continue
                oracle_type = type(oracle_value)
                test_type = type(test_value)
                if test_type is not oracle_type:
                    return (MarkusTest.Status.FAIL,
                            self.ERROR_MSGS['bad_col_type'].format(oracle_columns[j].name, oracle_type.__name__,
                                                                   test_type.__name__))
                checked_column_types.append(j)
            check_column_types = [j for j in check_column_types if j not in checked_column_types]
            # check 5, ordered variant: row contents + order
            if order_on and oracle_row != test_row:
                return (MarkusTest.Status.FAIL,
                        self.ERROR_MSGS['bad_row_content_order'].format(i, oracle_row, test_results[i]))
        # check 3: column types compatibility deferred trigger
        if check_column_types:
            return (MarkusTest.Status.FAIL,
                    self.ERROR_MSGS['bad_col_type_maybe'].format(oracle_columns[check_column_types[0]].name))

        # all good
        return MarkusTest.Status.PASS, ''

    def get_psql_dump(self, table_name, oracle_order_by=None, test_order_file=None):
        oracle_query, oracle_vars = self.select_query(schema_name=self.data_name, table_name=table_name,
                                                      order_by=oracle_order_by)
        oracle_command = ['psql', '-U', self.tester.user_name, '-d', self.tester.oracle_database, '-h', 'localhost',
                          '-c', self.tester.oracle_cursor.mogrify(oracle_query, oracle_vars)]
        test_command = ['psql', '-U', self.tester.user_name, '-d', self.tester.test_database, '-h', 'localhost', '-c']
        if test_order_file is not None:
            test_query = 'SET search_path TO %(schema)s;'
            test_vars = {'schema': psycopg2.extensions.AsIs(self.tester.schema_name)}
            with open(test_order_file) as test_order_open:
                test_query += test_order_open.read()
        else:
            test_query, test_vars = self.select_query(schema_name=self.tester.schema_name, table_name=table_name)
        test_command.extend([self.tester.test_cursor.mogrify(test_query, test_vars)])
        env = os.environ.copy()
        env['PGPASSWORD'] = self.tester.user_password
        oracle_proc = subprocess.run(oracle_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True,
                                     env=env, universal_newlines=True)
        test_proc = subprocess.run(test_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, env=env,
                                   universal_newlines=True)

        return oracle_proc.stdout, test_proc.stdout

    def run(self):

        # check that the submission exists
        if not os.path.isfile(self.test_file):
            message = self.ERROR_MSGS['no_submission'].format(self.test_file)
            return self.error(message)
        # check if ordering is required
        test_order_file = None
        oracle_order_by = self.test_extra.get('order_by')
        if oracle_order_by is not None:
            test_order_file = '{}_order{}'.format(self.test_name, os.path.splitext(self.test_file)[1])
            if not os.path.isfile(test_order_file):
                message = self.ERROR_MSGS['no_submission_order'].format(test_order_file)
                return self.error(message)
        try:
            # drop and recreate test schema + dataset, then fetch and compare results
            self.set_test_schema(self.data_file)
            test_results = self.get_test_results(table_name=self.test_name, sql_file=self.test_file,
                                                 sql_order_file=test_order_file)
            oracle_results = self.get_oracle_results(table_name=self.test_name, order_by=oracle_order_by)
            status, message = self.check_results(oracle_results, test_results, order_on=(oracle_order_by is not None))
            if status is MarkusTest.Status.PASS:
                return self.passed()
            else:
                oracle_solution, test_solution = self.get_psql_dump(table_name=self.test_name,
                                                                    oracle_order_by=oracle_order_by,
                                                                    test_order_file=test_order_file)
                return self.failed(message, oracle_solution, test_solution)
        except Exception as e:
            self.tester.oracle_connection.commit()
            self.tester.test_connection.commit()
            return self.error(message=str(e))


class MarkusSQLTester(MarkusTester):

    def __init__(self, specs, test_class=MarkusSQLTest):
        super().__init__(specs, test_class)
        system_user = getpass.getuser()
        for tester_spec in specs['tests']:
            if tester_spec['user'] == system_user:
                self.test_database = tester_spec['database']
                self.user_name = tester_spec['user']
                self.user_password = tester_spec['password']
                break
        self.oracle_database = specs['oracle_database']
        self.oracle_connection = None
        self.oracle_cursor = None
        self.test_connection = None
        self.test_cursor = None
        self.path_to_solution = specs['path_to_solution']
        self.schema_name = specs.get('schema_name', 'autotest')

    def before_tester_run(self):
        self.oracle_connection = psycopg2.connect(database=self.oracle_database, user=self.user_name,
                                                  password=self.user_password, host='localhost')
        self.oracle_cursor = self.oracle_connection.cursor()
        self.test_connection = psycopg2.connect(database=self.test_database, user=self.user_name,
                                                password=self.user_password, host='localhost')
        self.test_cursor = self.test_connection.cursor()

    def after_tester_run(self):
        if self.test_cursor:
            self.test_cursor.close()
        if self.test_connection:
            self.test_connection.close()
        if self.oracle_cursor:
            self.oracle_cursor.close()
        if self.oracle_connection:
            self.oracle_connection.close()
