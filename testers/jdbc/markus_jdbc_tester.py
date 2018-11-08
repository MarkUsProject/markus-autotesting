import collections
import os
import subprocess

from markus_sql_tester import MarkusSQLTester, MarkusSQLTest
from markus_tester import MarkusTester, MarkusTest


class MarkusJDBCTest(MarkusSQLTest):

    ERROR_MSGS = {
        'bad_javac': "Java compilation error: '{}'",
        'bad_java': "Java runtime error: '{}'"
    }
    ERROR_MSGS.update(MarkusSQLTest.ERROR_MSGS)
    JAVA_POINTS_KEY = 'JAVA'

    def __init__(self, tester, test_file, data_files, points, test_extra, feedback_open=None):
        super().__init__(tester, test_file, data_files, points, test_extra, feedback_open)

    @property
    def test_name(self):
        return self.test_file

    def check_java(self, order_on=False):
        java_command = ['java', '-cp', self.tester.java_classpath, self.__class__.__name__, self.tester.oracle_database,
                        self.tester.user_name, self.tester.user_password, self.tester.schema_name, self.test_name,
                        self.data_name, str(order_on), self.tester.test_database]
        java = subprocess.run(java_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                              check=True)

        return java

    def run(self):

        # drop and recreate test schema + dataset, then fetch and compare java results
        try:
            self.set_test_schema(self.data_file)
            order_on = self.test_extra.get('order_on', False)
            java = self.check_java(order_on)
            if java.stdout == MarkusTest.Status.FAIL.value:
                return self.failed(message=java.stderr)
            if java.stdout == MarkusTest.Status.ERROR.value:
                return self.error(message=java.stderr)
        except Exception as e:
            self.tester.oracle_connection.commit()
            self.tester.test_connection.commit()
            if isinstance(e, subprocess.CalledProcessError):
                msg = self.ERROR_MSGS['bad_java'].format(e.stdout + e.stderr)
            else:
                msg = str(e)
            return self.error(message=msg)
        if isinstance(self.points, collections.abc.Mapping):
            points_earned = self.points[self.JAVA_POINTS_KEY]
        else:
            return self.passed()
        # fetch and compare sql table results
        messages = []
        oracle_solutions = []
        test_solutions = []
        for table_name, table_points in sorted(self.points.items()):
            if table_name == self.JAVA_POINTS_KEY:
                continue
            try:
                test_results = self.get_test_results(table_name)
                oracle_results = self.get_oracle_results(table_name)
                status, message = self.check_results(oracle_results, test_results, order_on=False)
                if status is MarkusTest.Status.PASS:
                    points_earned += table_points
                else:
                    oracle_solution, test_solution = self.get_psql_dump(table_name)
                    messages.append('(Table {}) {}'.format(table_name, message))
                    oracle_solutions.append(oracle_solution)
                    test_solutions.append(test_solution)
            except Exception as e:
                self.tester.oracle_connection.commit()
                self.tester.test_connection.commit()
                messages.append('(Table {}) {}'.format(table_name, str(e)))
        if points_earned == self.points_total:
            return self.passed()
        else:
            return self.partially_passed(points_earned, message=', '.join(messages),
                                         oracle_solution='\n'.join(oracle_solutions),
                                         test_solution='\n'.join(test_solutions))


class MarkusJDBCTester(MarkusSQLTester):

    CLASS_DIR = 'classes'

    def __init__(self, specs, test_class=MarkusJDBCTest):
        super().__init__(specs, test_class)
        self.java_files = ['{}.java'.format(class_name) for class_name in set(
                              [test_name.partition('.')[0] for test_name in self.specs.tests])]
        self.java_classpath = '.:{}:{}'.format(os.path.join(specs['path_to_solution'], self.CLASS_DIR),
                                               specs['path_to_jdbc_jar'])

    def init_java(self):
        javac_command = ['javac', '-cp', self.java_classpath] + self.java_files
        subprocess.run(javac_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
                       check=True)

    def run(self):
        try:
            # check that the submission exists
            for java_file in self.java_files:
                if not os.path.isfile(java_file):
                    msg = MarkusJDBCTest.ERROR_MSGS['no_submission'].format(java_file)
                    print(MarkusTester.error_all(message=msg), flush=True)
                    return
            # check that the submission compiles
            try:
                self.init_java()
            except subprocess.CalledProcessError as e:
                msg = MarkusJDBCTest.ERROR_MSGS['bad_javac'].format(e.stdout)
                print(MarkusTester.error_all(message=msg), flush=True)
                return
        except Exception as e:
            print(MarkusTester.error_all(message=str(e)), flush=True)
            return
        super().run()
