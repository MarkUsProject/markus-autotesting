import json
import os
from pathlib import Path

import subprocess
import pytest
from ....testers.ai.ai_tester import AiTester, AiTest
from ....testers.specs import TestSpecs


@pytest.fixture(autouse=True, scope="session")
def set_required_env(tmp_path_factory):
    root = tmp_path_factory.mktemp("autotest")
    logs = root / "logs"
    logs.mkdir(exist_ok=True)
    os.environ.setdefault("WORKSPACE", "./")
    os.environ.setdefault("WORKER_LOG_DIR", "./")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("SUPERVISOR_URL", "http://localhost:9001")
    os.makedirs(os.environ["WORKER_LOG_DIR"], exist_ok=True)


def create_ai_tester():
    # test_data is an ARRAY; output must be one of the enum values
    parent_dir = str(Path(__file__).resolve().parent)
    spec = {
        "tester_type": "ai",
        "env_data": {"ai_feedback_version": "main"},
        "test_data": {
            "category": ["instructor"],
            "config": {
                "model": "openai",
                "prompt": "code_table",
                "scope": "code",
                "submission": parent_dir + "/fixtures/sample_submission.py",
                "submission_type": "python",
            },
            "extra_info": {
                "name": "AI FEEDBACK COMMENTS",
                "display_output": "instructors",
                "test_group_id": 17,
                "criterion": None,
            },
            "output": "overall_comment",
            "timeout": 30,
            "test_label": "Test A",
        },
        "_env": {"PYTHON": "/home/docker/.autotesting/scripts/128/ai_1/bin/python3"},
    }
    raw_spec = json.dumps(spec)
    return AiTester(specs=TestSpecs.from_json(raw_spec))


def test_ai_test_success_runs_properly():
    result = {"title": "Test A", "message": "Looks good", "status": "success"}
    test = AiTest(tester=create_ai_tester(), result=result)
    output = test.run()
    assert '"status": "pass"' in output
    assert "Looks good" in output


def test_ai_test_error_runs_properly():
    result = {"title": "Test A", "message": "Syntax error", "status": "error"}
    test = AiTest(tester=create_ai_tester(), result=result)
    output = test.run()
    assert '"status": "error"' in output
    assert "Syntax error" in output


def test_call_ai_feedback_success(monkeypatch):
    tester = create_ai_tester()
    mocked = subprocess.CompletedProcess(
        args=["python", "-m", "ai_feedback"], returncode=0, stdout="Great job!", stderr=""
    )
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: mocked)
    results = tester.call_ai_feedback()
    print(results)
    assert "Test A" in results
    assert results["Test A"]["status"] == "success"
    assert tester.overall_comments == ["Great job!"]
    assert tester.annotations == []


def test_call_ai_feedback_error(monkeypatch):
    tester = create_ai_tester()

    def raise_err(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args, stderr="Runtime error")

    monkeypatch.setattr(subprocess, "run", raise_err)
    results = tester.call_ai_feedback()
    assert results["Test A"]["status"] == "error"
    assert "Runtime error" in results["Test A"]["message"]
    assert tester.overall_comments == []
    assert tester.annotations == []


def test_run_prints_test_results(monkeypatch, capsys):
    tester = create_ai_tester()
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(args=a, returncode=0, stdout="Nice work", stderr=""),
    )
    monkeypatch.setattr(AiTest, "run", lambda self: '{"status": "success", "message": "Test Passed"}')
    tester.run()
    captured = capsys.readouterr()
    assert "Test Passed" in captured.out
