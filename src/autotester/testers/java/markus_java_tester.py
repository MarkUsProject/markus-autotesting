import enum
import json
import subprocess
from typing import Dict, Optional, IO, Type

from testers.markus_test_specs import MarkusTestSpecs
from testers.markus_tester import MarkusTester, MarkusTest, MarkusTestError


class MarkusJavaTest(MarkusTest):
    class JUnitStatus(enum.Enum):
        SUCCESSFUL = 1
        ABORTED = 2
        FAILED = 3

    ERRORS = {
        "bad_javac": 'Java compilation error: "{}"',
        "bad_java": 'Java runtime error: "{}"',
    }

    def __init__(self, tester: "MarkusJavaTester", result: Dict, feedback_open: Optional[IO] = None,) -> None:
        """
        Initialize a Java test created by tester.

        The result was created after running some junit tests.
        Test feedback will be written to feedback_open.
        """
        self.class_name, _sep, self.method_name = result["name"].partition(".")
        self.description = result.get("description")
        self.status = MarkusJavaTest.JUnitStatus[result["status"]]
        self.message = result.get("message")
        super().__init__(tester, feedback_open)

    @property
    def test_name(self) -> str:
        """ The name of this test """
        name = f"{self.class_name}.{self.method_name}"
        if self.description:
            name += f" ({self.description})"
        return name

    @MarkusTest.run_decorator
    def run(self) -> str:
        """
        Return a json string containing all test result information.
        """
        if self.status == MarkusJavaTest.JUnitStatus.SUCCESSFUL:
            return self.passed()
        elif self.status == MarkusJavaTest.JUnitStatus.FAILED:
            return self.failed(message=self.message)
        else:
            return self.error(message=self.message)


class MarkusJavaTester(MarkusTester):

    JAVA_TESTER_CLASS = "edu.toronto.cs.teach.MarkusJavaTester"

    def __init__(self, specs: MarkusTestSpecs, test_class: Type[MarkusJavaTest] = MarkusJavaTest) -> None:
        """
        Initialize a Java tester using the specifications in specs.

        This tester will create tests of type test_class.
        """
        super().__init__(specs, test_class)
        self.java_classpath = f'.:{self.specs["install_data", "path_to_tester_jars"]}/*'

    def compile(self) -> None:
        """
        Compile the junit tests specified in the self.specs specifications.
        """
        javac_command = ["javac", "-cp", self.java_classpath]
        javac_command.extend(self.specs["test_data", "script_files"])
        # student files imported by tests will be compiled on cascade
        subprocess.run(
            javac_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, check=True,
        )

    def run_junit(self) -> subprocess.CompletedProcess:
        """
        Run the junit tests specified in the self.specs specifications.
        """
        java_command = [
            "java",
            "-cp",
            self.java_classpath,
            MarkusJavaTester.JAVA_TESTER_CLASS,
        ]
        java_command.extend(self.specs["test_data", "script_files"])
        java = subprocess.run(
            java_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=True,
        )
        return java

    @MarkusTester.run_decorator
    def run(self) -> None:
        """
        Runs all tests in this tester.
        """
        # check that the submission compiles against the tests
        try:
            self.compile()
        except subprocess.CalledProcessError as e:
            msg = MarkusJavaTest.ERRORS["bad_javac"].format(e.stdout)
            raise MarkusTestError(msg) from e
        # run the tests with junit
        try:
            results = self.run_junit()
            if results.stderr:
                raise MarkusTestError(results.stderr)
        except subprocess.CalledProcessError as e:
            msg = MarkusJavaTest.ERRORS["bad_java"].format(e.stdout + e.stderr)
            raise MarkusTestError(msg) from e
        with self.open_feedback() as feedback_open:
            for result in json.loads(results.stdout):
                test = self.test_class(self, result, feedback_open)
                result_json = test.run()
                print(result_json, flush=True)
