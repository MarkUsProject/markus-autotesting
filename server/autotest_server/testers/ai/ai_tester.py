import sys

from ..tester import Test
from ..tester import Tester
from ..specs import TestSpecs
import subprocess
from typing import Type


class AITest(Test):
    def __init__(
        self,
        tester: "AITester",
        result: dict = None,
    ):
        self._test_name = result["title"]
        self.message = result["message"]
        self.status = result["status"]
        super().__init__(tester)

    @property
    def test_name(self) -> str:
        """The name of this test"""
        return self._test_name

    @Test.run_decorator
    def run(self) -> str:
        """
        Return a json string containing all test result information.
        """
        if self.status == "success":
            return self.passed(message=self.message)
        else:
            return self.error(message=self.message)


class AITester(Tester):
    def __init__(
        self,
        specs: TestSpecs,
        test_class: Type[AITest] = AITest,
        resource_settings: list[tuple[int, tuple[int, int]]] | None = None,
    ) -> None:
        """
        Initialize a new AIFeedbackTester using the specifications in the specs
        """
        super().__init__(specs, test_class, resource_settings=resource_settings)
        self.annotations = []
        self.overall_comments = []

    def call_ai_feedback(self) -> dict:
        """
        Call ai_feedback CLI using subprocess and arguments from self.specs.
        Supports all standard arguments from ai_feedback.
        """
        results = {}
        for test_group in self.specs["test_data"]:
            config = test_group["config"]
            title = test_group["title"]
            cmd = [sys.executable, "-m", "ai_feedback"]
            for key, value in config.items():
                cmd.extend(["--" + key, str(value)])

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=test_group["timeout"])
                results[title] = {"title": title, "status": "success", "message": result.stdout}
                if test_group["output"] == "overall":
                    self.overall_comments.append(result.stdout)
                elif test_group["output"] == "annotation":
                    self.annotations.append(result.stdout)

            except subprocess.CalledProcessError as e:
                results[title] = {"title": title, "status": "error", "message": e.stderr or str(e)}
            except ValueError as ve:
                results[title] = {"title": title, "status": "error", "message": str(ve)}

        return results

    @Tester.run_decorator
    def run(self) -> None:
        """
        Gets the AI feedback based on the specifications in the specs.
        """
        results = self.call_ai_feedback()
        for _, result in results.items():
            test = self.test_class(self, result=result)
            print(test.run(), flush=True)
