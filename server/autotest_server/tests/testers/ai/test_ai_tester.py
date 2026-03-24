import json
import os
from pathlib import Path

import subprocess
import pytest
from ....testers.ai.ai_tester import AiTester, AiTest
from ....testers.specs import TestSpecs

DEFAULT_REMOTE_URL = "https://polymouth.teach.cs.toronto.edu:443/chat"
FIXTURES_DIR = str(Path(__file__).resolve().parent / "fixtures")


@pytest.fixture(autouse=True, scope="session")
def set_required_env():
    os.environ.setdefault("WORKSPACE", "./")
    os.environ.setdefault("WORKER_LOG_DIR", "./")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("SUPERVISOR_URL", "http://localhost:9001")
    os.makedirs(os.environ["WORKER_LOG_DIR"], exist_ok=True)


def _make_spec(output="overall_comment", config_overrides=None):
    """Build a test spec with sensible defaults. Override only what varies."""
    config = {
        "model": "remote",
        "prompt": "code_table",
        "scope": "code",
        "submission": FIXTURES_DIR + "/sample_submission.py",
        "submission_type": "python",
        "remote_url": DEFAULT_REMOTE_URL,
    }
    if config_overrides:
        config.update(config_overrides)
    return {
        "tester_type": "ai",
        "env_data": {"ai_feedback_version": "main"},
        "test_data": {
            "category": ["instructor"],
            "config": config,
            "extra_info": {
                "name": "AI FEEDBACK COMMENTS",
                "display_output": "instructors",
                "test_group_id": 17,
                "criterion": None,
            },
            "output": output,
            "timeout": 30,
            "test_label": "Test A",
        },
        "_env": {"PYTHON": "/home/docker/.autotesting/scripts/128/ai_1/bin/python3"},
    }


def _make_tester(**kwargs):
    return AiTester(specs=TestSpecs.from_json(json.dumps(_make_spec(**kwargs))))


def _mock_subprocess(monkeypatch, *, stdout="OK", stderr=""):
    mocked = subprocess.CompletedProcess(
        args=["python", "-m", "ai_feedback"], returncode=0, stdout=stdout, stderr=stderr
    )
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: mocked)


@pytest.mark.parametrize(
    "status,expected_status,message",
    [
        ("success", "pass", "Looks good"),
        ("error", "error", "Syntax error"),
    ],
)
def test_ai_test_result_formatting(status, expected_status, message):
    result = {"title": "Test A", "message": message, "status": status}
    test = AiTest(tester=_make_tester(), result=result)
    output = test.run()
    assert f'"status": "{expected_status}"' in output
    assert message in output


def test_overall_comment_output(monkeypatch):
    tester = _make_tester()
    _mock_subprocess(monkeypatch, stdout="Great job!")
    results = tester.call_ai_feedback()
    assert results["Test A"]["status"] == "success"
    assert tester.overall_comments == ["Great job!"]
    assert tester.annotations == []


def test_annotations_output(monkeypatch):
    annotation_data = {"annotations": [{"line": 1, "text": "Good variable name"}]}
    tester = _make_tester(output="annotations")
    _mock_subprocess(monkeypatch, stdout=json.dumps(annotation_data))
    results = tester.call_ai_feedback()
    assert results["Test A"]["status"] == "success"
    assert len(tester.annotations) == 1
    assert tester.annotations[0]["text"] == "Good variable name"


def test_message_output(monkeypatch):
    tester = _make_tester(output="message")
    _mock_subprocess(monkeypatch, stdout="Score: 8/10")
    results = tester.call_ai_feedback()
    assert results["Test A"]["status"] == "success"
    assert results["Test A"]["message"] == "Score: 8/10"


def test_subprocess_error(monkeypatch):
    tester = _make_tester()

    def raise_err(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "cmd", stderr="Runtime error")

    monkeypatch.setattr(subprocess, "run", raise_err)
    results = tester.call_ai_feedback()
    assert results["Test A"]["status"] == "error"
    assert "Runtime error" in results["Test A"]["message"]


def test_rejects_non_remote_model():
    tester = _make_tester(config_overrides={"model": "openai"})
    results = tester.call_ai_feedback()
    assert results["Test A"]["status"] == "error"
    assert "Unsupported model type" in results["Test A"]["message"]
    assert "openai" in results["Test A"]["message"]


def test_missing_submission_file():
    tester = _make_tester(config_overrides={"submission": FIXTURES_DIR + "/nonexistent.py"})
    results = tester.call_ai_feedback()
    assert results["Test A"]["status"] == "error"
    assert "Could not find submission file" in results["Test A"]["message"]


def test_opt_out_skips_feedback(tmp_path):
    opt_out_file = tmp_path / "opt_out.py"
    opt_out_file.write_text("# NO_EXTERNAL_AI_FEEDBACK\ndef foo(): pass\n")
    tester = _make_tester(config_overrides={"submission": str(opt_out_file)})
    results = tester.call_ai_feedback()
    assert results["Test A"]["status"] == "success"
    assert "NO_EXTERNAL_AI_FEEDBACK" in results["Test A"]["message"]


def test_run_prints_output(monkeypatch, capsys):
    tester = _make_tester()
    _mock_subprocess(monkeypatch, stdout="Nice work")
    monkeypatch.setattr(AiTest, "run", lambda self: '{"status": "success", "message": "Test Passed"}')
    tester.run()
    captured = capsys.readouterr()
    assert "Test Passed" in captured.out
