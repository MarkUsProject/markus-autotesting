import os
import subprocess
import tempfile
import xml.etree.ElementTree as eTree
from glob import glob
from typing import Type, List, Set
from ..tester import Tester, Test, TestError
from ..specs import TestSpecs


class JavaTest(Test):
    def __init__(self, tester, result):
        self._test_name = result["name"]
        self.status = result["status"]
        self.message = result["message"]
        super().__init__(tester)

    @property
    def test_name(self):
        return self._test_name

    @Test.run_decorator
    def run(self):
        if self.status == "success":
            return self.passed(message=self.message)
        elif self.status == "failure":
            return self.failed(message=self.message)
        else:
            return self.error(message=self.message)


class JavaTester(Tester):
    JUNIT_TESTER_JAR = os.path.join(os.path.dirname(__file__), "lib", "junit-platform-console-standalone.jar")
    JUNIT_JUPITER_RESULT = "TEST-junit-jupiter.xml"
    JUNIT_VINTAGE_RESULT = "TEST-junit-vintage.xml"

    def __init__(
        self,
        specs: TestSpecs,
        test_class: Type[JavaTest] = JavaTest,
        resource_settings: list[tuple[int, tuple[int, int]]] | None = None,
    ) -> None:
        """
        Initialize a Java tester using the specifications in specs.

        This tester will create tests of type test_class.
        """
        super().__init__(specs, test_class, resource_settings=resource_settings)
        classpath = self.specs.get("test_data", "classpath", default=".") or "."
        self.java_classpath = ":".join(self._parse_file_paths(classpath))
        self.out_dir = tempfile.TemporaryDirectory(dir=os.getcwd())
        self.reports_dir = tempfile.TemporaryDirectory(dir=os.getcwd())

    @staticmethod
    def _parse_file_paths(glob_string: str) -> List[str]:
        """
        Return the real (absolute) paths of all files described by the glob <glob_string>.
        Only files that exist in the current directory (or its subdirectories) are returned.
        """
        curr_path = os.path.realpath(".")
        return [x for p in glob_string.split(":") for x in glob(os.path.realpath(p)) if curr_path in x]

    def _get_sources(self) -> Set:
        """
        Return all java source files for this test.
        """
        sources = self.specs.get("test_data", "sources_path", default="")
        scripts = ":".join(self.specs["test_data", "script_files"] + [sources])
        return {path for path in self._parse_file_paths(scripts) if os.path.splitext(path)[1] == ".java"}

    def _parse_failure_error(self, failure, error):
        """
        Return a dictionary containing a status and message for either a failure, error, or both. If both
        an error and failure are present, the message includes information for both.
        """
        result = {}
        if failure is not None and error is not None:
            failure_message = self._parse_failure_error(failure, None)["message"]
            error_message = self._parse_failure_error(None, error)["message"]
            result["status"] = "error"
            result["message"] = "\n\n".join([error_message, failure_message])
        elif failure is not None:
            result["status"] = "failure"
            result["message"] = f'{failure.attrib.get("type", "")}: {failure.attrib.get("message", "")}'
        elif error is not None:
            result["status"] = "error"
            result["message"] = f'{error.attrib.get("type", "")}: {error.attrib.get("message", "")}'
        return result

    def _parse_junitxml(self):
        """
        Parse junit results and yield a hash containing result data for each testcase.
        """
        for xml_filename in [self.JUNIT_JUPITER_RESULT, self.JUNIT_VINTAGE_RESULT]:
            tree = eTree.parse(os.path.join(self.reports_dir.name, xml_filename))
            root = tree.getroot()
            for testcase in root.iterfind("testcase"):
                result = {}
                classname = testcase.attrib["classname"]
                testname = testcase.attrib["name"]
                result["name"] = "{}.{}".format(classname, testname)
                result["time"] = float(testcase.attrib.get("time", 0))
                failure = testcase.find("failure")
                error = testcase.find("error")
                fe_result = self._parse_failure_error(failure, error)
                if fe_result:
                    result.update(fe_result)
                else:
                    result["status"] = "success"
                    result["message"] = ""
                yield result

    def compile(self) -> subprocess.CompletedProcess:
        """
        Compile the junit tests specified in the self.specs specifications.
        """
        classpath = f"{self.java_classpath}:{self.JUNIT_TESTER_JAR}"
        javac_command = ["javac", "-cp", classpath, "-d", self.out_dir.name]
        javac_command.extend(self._get_sources())
        # student files imported by tests will be compiled on cascade
        return subprocess.run(
            javac_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
        )

    def run_junit(self) -> subprocess.CompletedProcess:
        """
        Run the junit tests specified in the self.specs specifications.
        """
        java_command = [
            "java",
            "-jar",
            self.JUNIT_TESTER_JAR,
            f"-cp={self.java_classpath}:{self.out_dir.name}",
            f"--reports-dir={self.reports_dir.name}",
        ]
        classes = [f"-c={os.path.splitext(os.path.basename(f))[0]}" for f in self.specs["test_data", "script_files"]]
        java_command.extend(classes)
        java = subprocess.run(
            java_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=False
        )
        return java

    @Tester.run_decorator
    def run(self) -> None:
        """
        Runs all tests in this tester.
        """
        # check that the submission compiles against the tests
        try:
            compile_result = self.compile()
            if compile_result.stderr:
                raise TestError(compile_result.stderr)
        except subprocess.CalledProcessError as e:
            raise TestError(e)
        # run the tests with junit
        try:
            results = self.run_junit()
            if results.stderr:
                raise TestError(results.stderr)
        except subprocess.CalledProcessError as e:
            raise TestError(e)
        for result in self._parse_junitxml():
            test = self.test_class(self, result)
            result_json = test.run()
            print(result_json, flush=True)
