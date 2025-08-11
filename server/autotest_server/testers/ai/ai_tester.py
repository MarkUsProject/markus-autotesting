import json
import os
import sys

from ..tester import Test, Tester
from ..specs import TestSpecs
import subprocess
from typing import Type
from dotenv import load_dotenv


class AiTest(Test):
    def __init__(
        self,
        tester: "AiTester",
        result: dict = None,
    ):
        self._test_name = result["title"]
        self.message = result.get("message", "")
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
        if self.status in ("success", "pass"):
            return self.passed(message=self.message)
        elif self.status == "partial":
            return self.partially_passed(points_earned=1, message=self.message)  # update points as needed
        else:
            return self.error(message=self.message)


class AiTester(Tester):
    def __init__(
        self,
        specs: TestSpecs,
        test_class: Type[AiTest] = AiTest,
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
        load_dotenv()
        env = os.environ.copy()

        test_data = self.specs["test_data"]
        if isinstance(test_data, dict):
            test_data = [test_data]
        for test_group in test_data:
            config = test_group.get("config", {})
            title = test_group.get("title", "Unnamed Test")
            timeout = test_group.get("timeout", 60)
            output_mode = test_group.get("output")
            cmd = [sys.executable, "-m", "ai_feedback"]
            for key, value in config.items():
                cmd.extend(["--" + key, str(value)])

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout, env=env)
                output = result.stdout
                if output_mode == "overall_comment":
                    self.overall_comments.append(output)
                    results[title] = {"title": title, "status": "success"}
                elif output_mode == "annotations":
                    try:
                        annotations_data = json.loads(output)
                        annotations = annotations_data.get("annotations", annotations_data)
                    except json.JSONDecodeError as e:
                        raise ValueError(f"Invalid JSON in output for {title}: {e}")
                    self.annotations.extend(annotations)
                    results[title] = {"title": title, "status": "success"}
                elif output_mode == "message":
                    results[title] = {"title": title, "status": "success", "message": output}

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
            test_result = test.run()
            print(test_result, flush=True)

    def after_tester_run(self) -> None:
        """Print all Markus metadata from the tests."""
        if self.annotations:
            print(self.test_class.format_annotations(self.annotations))
        if self.overall_comments:
            print(self.test_class.format_overall_comment(self.overall_comments, separator="\n\n"))
