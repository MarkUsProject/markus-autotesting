import json
import os
import re
import sys

from ..tester import Test, Tester
from ..specs import TestSpecs
import subprocess
from typing import Optional, Type
from urllib.parse import urlsplit
from dotenv import load_dotenv
from pathlib import Path
import PyPDF2

# Models the AI tester is allowed to invoke. "remote" routes to the
# markus-ai-server proxy (local models); "openai-remote" routes to the
# self-hosted LiteLLM gateway (cloud OpenAI, telemetry + budget enforced).
# Any other model would reach a cloud provider untracked, so it is rejected.
ALLOWED_MODELS = ("remote", "openai-remote")

# Categories ordered most-privileged first. A job's categories array collapses
# to a single role for telemetry; when more than one is present the most
# privileged wins (see ai-telemetry-gateway decision-record §4).
_ROLE_PRIORITY = ("instructor", "student")

# The four spec attribution fields live inside the MarkUs file_url, shaped
# <instance>/api/courses/<course_id>/assignments/<assignment_id>/groups/<group_id>/submission_files
_FILE_URL_RE = re.compile(
    r"/api/courses/(?P<course_id>\d+)"
    r"/assignments/(?P<assignment_id>\d+)"
    r"/groups/(?P<group_id>\d+)/submission_files"
)


def _resolve_category(categories: list) -> Optional[str]:
    """Collapse the categories array to one role; most-privileged wins."""
    for role in _ROLE_PRIORITY:
        if role in categories:
            return role
    return categories[0] if categories else None


def build_spend_metadata(files_url: Optional[str], categories: Optional[list], batch_id) -> dict:
    """Extract the six attribution fields the gateway records on every call.

    Raises ValueError when ``files_url`` does not match the expected MarkUs
    shape. A malformed URL is a programming error in MarkUs, not a recoverable
    runtime condition, so we fail loud rather than emit a ledger row with
    nonsense identifiers.
    """
    parts = urlsplit(files_url or "")
    match = _FILE_URL_RE.search(parts.path)
    if not parts.netloc or match is None:
        raise ValueError(
            f"Cannot extract attribution from file_url {files_url!r}: expected "
            ".../api/courses/<id>/assignments/<id>/groups/<id>/submission_files"
        )
    return {
        "instance": parts.netloc,
        "course_id": int(match["course_id"]),
        "assignment_id": int(match["assignment_id"]),
        "group_id": int(match["group_id"]),
        "batch_id": batch_id,
        "category": _resolve_category(categories or []),
    }


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

        # Restrict to the gateway-fronted models — prevent untracked cloud access.
        model = config.get("model", "")
        if model not in ALLOWED_MODELS:
            allowed = ", ".join(f"'{m}'" for m in ALLOWED_MODELS)
            results[test_label] = {
                "title": test_label,
                "status": "error",
                "message": f'Unsupported model type: "{model}". Allowed models: {allowed}.',
            }
            return results

        submission_file = config.get("submission")
        try:
            disallowed_term_in_file = self._term_in_file(submission_file)
        except FileNotFoundError:
            results[test_label] = {
                "title": test_label,
                "status": "error",
                "message": f'Could not find submission file "{submission_file}"',
            }
            return results

        if disallowed_term_in_file:
            results[test_label] = {
                "title": test_label,
                "status": "success",
                "message": "Student included the text 'NO_EXTERNAL_AI_FEEDBACK' in their submission file. No AI "
                "feedback generated.",
            }
            return results

        # Gateway-bound calls carry MarkUs attribution so the ledger can record
        # per-course spend and the gatekeeper can enforce budgets. The worker
        # injects the raw pieces under "_attribution"; we parse them here, at
        # the point the AI feedback library is about to be invoked.
        if model == "openai-remote":
            attribution = self.specs.get("_attribution", default={})
            try:
                metadata = build_spend_metadata(
                    attribution.get("files_url"),
                    attribution.get("categories"),
                    attribution.get("batch_id"),
                )
            except ValueError as ve:
                results[test_label] = {"title": test_label, "status": "error", "message": str(ve)}
                return results
            env["LITELLM_SPEND_METADATA"] = json.dumps(metadata)

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
