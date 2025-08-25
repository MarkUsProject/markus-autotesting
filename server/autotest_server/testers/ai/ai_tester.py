import json
import os
import sys

from ..tester import Test, Tester
from ..specs import TestSpecs
import subprocess
from typing import Type
from dotenv import load_dotenv
from pathlib import Path
import PyPDF2


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
        if self.status == "success":
            return self.passed(message=self.message)
        elif self.status == "partial":
            return self.partially_passed(points_earned=1, message=self.message)
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
        self.tags = []

    def call_ai_feedback(self) -> dict:
        """
        Call ai_feedback CLI using subprocess and arguments from self.specs.
        Supports all standard arguments from ai_feedback.
        """
        results = {}
        load_dotenv()
        env = os.environ.copy()

        test_group = self.specs["test_data"]

        config = test_group.get("config", {})
        test_label = test_group.get("test_label")
        timeout = test_group.get("timeout", 30)
        output_mode = test_group.get("output")
        cmd = [sys.executable, "-m", "ai_feedback"]

        submission_file = config.get("submission")
        if self._term_in_file(submission_file):
            results[test_label] = {
                "title": test_label,
                "status": "success",
                "message": "Student included the text 'NO_EXTERNAL_AI_FEEDBACK' in their submission file. No AI "
                "feedback generated.",
            }
            return results

        for key, value in config.items():
            cmd.extend(["--" + key, str(value)])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout, env=env)
            output = result.stdout

            parsed = None
            try:
                parsed = json.loads(output)
            except json.JSONDecodeError:
                pass
            if isinstance(parsed, dict):
                if "tags" in parsed:
                    tags = parsed["tags"]
                    self.tags.extend(tags)
                if "output" in parsed:
                    output = parsed["output"]

            if output_mode == "overall_comment":
                self.overall_comments.append(output)
                results[test_label] = {"title": test_label, "status": "success"}
            elif output_mode == "annotations":
                if parsed is None:
                    raise ValueError(f"Unable to parse the output of '{output}'")
                annotations = parsed.get("annotations", parsed)
                self.annotations.extend(annotations)
                results[test_label] = {"title": test_label, "status": "success"}
            elif output_mode == "message":
                results[test_label] = {"title": test_label, "status": "success", "message": output}

        except subprocess.CalledProcessError as e:
            results[test_label] = {"title": test_label, "status": "error", "message": e.stderr or str(e)}
        except ValueError as ve:
            results[test_label] = {"title": test_label, "status": "error", "message": str(ve)}

        return results

    def _term_in_file(self, file_path: str) -> bool:
        """Check for NO_EXTERNAL_AI_FEEDBACK string in submission file"""
        term = "NO_EXTERNAL_AI_FEEDBACK"
        path = Path(file_path)

        try:
            if path.suffix.lower() == ".pdf":
                with open(file_path, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        text = page.extract_text() or ""
                        if term in text:
                            return True
                return False
            else:
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if term in line:
                            return True
                return False
        except FileNotFoundError:
            return True

    @Tester.run_decorator
    def run(self) -> None:
        """
        Gets the AI feedback based on the specifications in the specs.
        """
        results = self.call_ai_feedback()
        for result in results.values():
            test = self.test_class(self, result=result)
            test_result = test.run()
            print(test_result, flush=True)

    def after_tester_run(self) -> None:
        """Print all Markus metadata from the tests."""
        if self.annotations:
            print(self.test_class.format_annotations(self.annotations))
        if self.overall_comments:
            print(self.test_class.format_overall_comment(self.overall_comments, separator="\n\n"))
        if self.tags:
            print(self.test_class.format_tags(self.tags))
