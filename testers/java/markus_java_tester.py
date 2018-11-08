import contextlib
import enum
import json
import subprocess

from markus_tester import MarkusTester, MarkusTest, MarkusTestSpecs


class MarkusJavaTest(MarkusTest):

    class JUnitStatus(enum.Enum):
        SUCCESSFUL = 1
        ABORTED = 2
        FAILED = 3

    ERRORS = {
        'bad_javac': 'Java compilation error: "{}"',
        'bad_java': 'Java runtime error: "{}"'
    }

    def __init__(self, tester, feedback_open, result):
        self.class_name, _sep, self.method_name = result['name'].partition('.')
        test_file = f'{self.class_name}.java'
        all_points = tester.specs.matrix[test_file][MarkusTestSpecs.MATRIX_NODATA_KEY]
        points = all_points.get(self.method_name, all_points.get(self.class_name, 1))
        self.description = result.get('description')
        self.status = MarkusJavaTest.JUnitStatus[result['status']]
        self.message = result.get('message', None)
        super().__init__(tester, test_file, [MarkusTestSpecs.MATRIX_NODATA_KEY], points, {}, feedback_open)

    @property
    def test_name(self):
        name = f'{self.class_name}.{self.method_name}'
        if self.description:
            name += f' ({self.description})'

        return name

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
        self.java_classpath = f'.:{specs["path_to_tester_jars"]}/*'

    def compile(self):
        javac_command = ['javac', '-cp', self.java_classpath] + [test_file for test_file in self.specs.tests]
        # student files imported by tests will be compiled on cascade
        subprocess.run(javac_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
                       check=True)

    def run_junit(self):
        java_command = ['java', '-cp', self.java_classpath, MarkusJavaTester.JAVA_TESTER_CLASS] + \
                       [test_file for test_file in self.specs.tests]
        java = subprocess.run(java_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                              check=True)
        return java

    def run(self):
        # TODO Create an interface in markus_tester for running all tests at once, when using native test libraries
        try:
            # check that the submission compiles against the tests
            try:
                self.compile()
            except subprocess.CalledProcessError as e:
                msg = MarkusJavaTest.ERRORS['bad_javac'].format(e.stdout)
                print(MarkusTester.error_all(message=msg), flush=True)
                return
            # run the tests with junit
            try:
                results = self.run_junit()
                if results.stderr:
                    print(MarkusTester.error_all(message=results.stderr), flush=True)
                    return
            except subprocess.CalledProcessError as e:
                msg = MarkusJavaTest.ERRORS['bad_java'].format(e.stdout + e.stderr)
                print(MarkusTester.error_all(message=msg), flush=True)
                return
            with contextlib.ExitStack() as stack:
                feedback_open = (stack.enter_context(open(self.specs.feedback_file, 'w'))
                                 if self.specs.feedback_file is not None
                                 else None)
                for result in json.loads(results.stdout):
                    test = self.test_class(self, feedback_open, result)
                    xml = test.run()
                    print(xml, flush=True)
        except Exception as e:
            print(MarkusTester.error_all(message=str(e)), flush=True)
            return
