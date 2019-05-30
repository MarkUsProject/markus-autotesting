import enum
import json
import subprocess

from testers.markus_tester import MarkusTester, MarkusTest


class MarkusJavaTest(MarkusTest):

    class JUnitStatus(enum.Enum):
        SUCCESSFUL = 1
        ABORTED = 2
        FAILED = 3

    ERRORS = {
        'bad_javac': 'Java compilation error: "{}"',
        'bad_java': 'Java runtime error: "{}"'
    }

    def __init__(self, tester, result, feedback_open=None):
        self.class_name, _sep, self.method_name = result['name'].partition('.')
        self.description = result.get('description')
        self.status = MarkusJavaTest.JUnitStatus[result['status']]
        self.message = result.get('message')
        super().__init__(tester, feedback_open)

    @property
    def test_name(self):
        name = f'{self.class_name}.{self.method_name}'
        if self.description:
            name += f' ({self.description})'
        return name

    @MarkusTest.run_decorator
    def run(self):
        if self.status == MarkusJavaTest.JUnitStatus.SUCCESSFUL:
            return self.passed()
        elif self.status == MarkusJavaTest.JUnitStatus.FAILED:
            return self.failed(message=self.message)
        else:
            return self.error(message=self.message)


class MarkusJavaTester(MarkusTester):

    JAVA_TESTER_CLASS = 'edu.toronto.cs.teach.MarkusJavaTester'

    def __init__(self, specs, test_class=MarkusJavaTest):
        super().__init__(specs, test_class)
        self.java_classpath = f'.:{self.specs["install_data", "path_to_tester_jars"]}/*'

    def compile(self):
        javac_command = ['javac', '-cp', self.java_classpath]
        javac_command.extend(self.specs['test_data', 'script_files'])
        # student files imported by tests will be compiled on cascade
        subprocess.run(javac_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
                       check=True)

    def run_junit(self):
        java_command = ['java', '-cp', self.java_classpath, MarkusJavaTester.JAVA_TESTER_CLASS]
        java_command.extend(self.specs.get['test_data', 'script_files'])
        java = subprocess.run(java_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                              check=True)
        return java

    @MarkusTester.run_decorator
    def run(self):
        # check that the submission compiles against the tests
        try:
            self.compile()
        except subprocess.CalledProcessError as e:
            msg = MarkusJavaTest.ERRORS['bad_javac'].format(e.stdout)
            raise type(e)(msg) from e
        # run the tests with junit
        try:
            results = self.run_junit()
            if results.stderr:
                raise Exception(results.stderr)
        except subprocess.CalledProcessError as e:
            msg = MarkusJavaTest.ERRORS['bad_java'].format(e.stdout + e.stderr)
            raise type(e)(msg) from e
        with self.open_feedback() as feedback_open:
            for result in json.loads(results.stdout):
                test = self.test_class(self, result, feedback_open)
                result_json = test.run()
                print(result_json, flush=True)
