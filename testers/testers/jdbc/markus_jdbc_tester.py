import os
import subprocess

from testers.sql.markus_sql_tester import MarkusSQLTester, MarkusSQLTest
from testers.markus_tester import MarkusTester, MarkusTest


class MarkusJDBCTest(MarkusSQLTest):

    ERROR_MSGS = {
        'bad_javac': "Java compilation error: '{}'",
        'bad_java': "Java runtime error: '{}'"
    }
    ERROR_MSGS.update(MarkusSQLTest.ERROR_MSGS)

    def __init__(self, tester, **kwargs):
        self.tables = kwargs.get('tables', [])
        self.order_on = kwargs.get('order_on', False)

        class_file = kwargs['class_file']
        self.class_name = os.path.splitext(os.path.basename(class_file))[0]
        self.method = kwargs.get('method', '')

        super().__init__(tester, **kwargs)
        
        if not self.data_file:
            self.schema_name = self.tester.schema_name

        self.java_points = 1
        self.points_total = len(self.tables) + 1

    @property
    def test_name(self):
        if self.data_file:
            return f'{self.class_name}.{self.method}.{self.data_name}'
        else:
            return f'{self.class_name}.{self.method}'

    def check_java(self):
        java_command = ['java', '-cp', self.tester.java_classpath, self.__class__.__name__, self.tester.oracle_database,
                        self.tester.user_name, self.tester.user_password, self.tester.schema_name, self.test_name,
                        self.schema_name, str(self.order_on), self.tester.test_database]
        java = subprocess.run(java_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                              check=True)

        return java

    @MarkusTest.run_decorator
    def run(self):
        # drop and recreate test schema + dataset, then fetch and compare java results
        try:
            self.set_test_schema(self.data_file)
            java = self.check_java()
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
        points_earned = self.java_points
        # fetch and compare sql table results
        messages = []
        oracle_solutions = []
        test_solutions = []
        for table in self.tables:
            try:
                test_results = self.get_test_results(table)
                oracle_results = self.get_oracle_results(table)
                status, message = self.check_results(oracle_results, test_results)
                if status is MarkusTest.Status.PASS:
                    points_earned += 1
                else:
                    oracle_solution, test_solution = self.get_psql_dump(table)
                    messages.append('(Table {}) {}'.format(table, message))
                    oracle_solutions.append(oracle_solution)
                    test_solutions.append(test_solution)
            except Exception as e:
                self.tester.oracle_connection.commit()
                self.tester.test_connection.commit()
                messages.append('(Table {}) {}'.format(table, str(e)))
        if points_earned == self.points_total:
            return self.passed()
        else:
            return self.partially_passed(points_earned, message=', '.join(messages),
                                         oracle_solution='\n'.join(oracle_solutions),
                                         test_solution='\n'.join(test_solutions))


class MarkusJDBCTester(MarkusSQLTester):

    def __init__(self, specs, test_class=MarkusJDBCTest):
        super().__init__(specs, test_class)
        java_files = (group.get('class_file') for group in self.specs['test_data', 'class_files'])
        self.java_files = [jf for jf in java_files if jf]
        solution_path = os.path.join(self.specs['env_loc'], self.SOLUTION_DIR)
        self.java_classpath = '.:{}:{}'.format(solution_path, self.specs['install_data', 'path_to_jdbc_jar'])

    def init_java(self):
        javac_command = ['javac', '-cp', self.java_classpath] + self.java_files
        subprocess.run(javac_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
                       check=True)

    @MarkusTester.run_decorator
    def run(self):
        # check that the submission exists
        for java_file in self.java_files:
            if not os.path.isfile(java_file):
                msg = MarkusJDBCTest.ERROR_MSGS['no_submission'].format(java_file)
                raise Exception(msg)
        # check that the submission compiles
        try:
            self.init_java()
        except subprocess.CalledProcessError as e:
            msg = MarkusJDBCTest.ERROR_MSGS['bad_javac'].format(e.stdout)
            raise type(e)(msg) from e
        feedback_file = self.specs.get('test_data', 'feedback_file_name')
        with MarkusTester.open_feedback(feedback_file) as feedback_open:
            class_groups = self.specs['test_data', 'class_files']
            test_kwargs = []
            env_name = os.path.basename(self.specs['env_loc'])
            for group in class_groups:
                class_file = group['class_file']
                if group.get('test_connection'):
                    test_kwargs.append(dict(class_file=class_file, method='CONNECTION'))
                if group.get('test_disconnection'):
                    test_kwargs.append(dict(class_file=class_file, method='DISCONNECTION'))
                for method_group in group.get('class_methods'):
                    method = method_group.get('class_method', '')
                    for data_group in method_group.get('data_files', []):
                        data_file = data_group.get('data_file', '')
                        tables = data_group.get('tables', [])
                        test_kwargs.append(dict(class_file=class_file,
                                                method=method,
                                                data_file=data_file,
                                                schema_prefix=env_name,
                                                tables=tables))
            for kwargs in test_kwargs:
                test = self.test_class(self, **{**kwargs, 'feedback_open': feedback_open})
                print(test.run())
