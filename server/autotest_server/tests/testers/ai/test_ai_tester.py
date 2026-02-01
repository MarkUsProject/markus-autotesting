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


@pytest.fixture(autouse=True)
def setup_whitelist_file():
    """Create whitelist_urls.txt in the current directory for tests."""
    whitelist_path = Path("whitelist_urls.txt")
    whitelist_path.write_text("https://polymouth.teach.cs.toronto.edu:443/chat\n")
    yield
    if whitelist_path.exists():
        whitelist_path.unlink()


def create_ai_tester(remote_url=None):
    # test_data is an ARRAY; output must be one of the enum values
    parent_dir = str(Path(__file__).resolve().parent)
    config = {
        "model": "remote",
        "prompt": "code_table",
        "scope": "code",
        "submission": parent_dir + "/fixtures/sample_submission.py",
        "submission_type": "python",
    }
    if remote_url is not None:
        config["remote_url"] = remote_url
    spec = {
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


def test_call_ai_feedback_rejects_non_whitelisted_url():
    tester = create_ai_tester(remote_url="https://evil-server.com/steal-data")
    results = tester.call_ai_feedback()
    assert results["Test A"]["status"] == "error"
    assert "not whitelisted" in results["Test A"]["message"]
    assert "evil-server.com" in results["Test A"]["message"]


def test_call_ai_feedback_accepts_whitelisted_url(monkeypatch):
    tester = create_ai_tester(remote_url="https://polymouth.teach.cs.toronto.edu:443/chat")
    mocked = subprocess.CompletedProcess(
        args=["python", "-m", "ai_feedback"], returncode=0, stdout="Feedback", stderr=""
    )
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: mocked)
    results = tester.call_ai_feedback()
    assert results["Test A"]["status"] == "success"


def test_call_ai_feedback_missing_whitelist_file():
    # Remove the whitelist file to simulate missing config
    whitelist_path = Path("whitelist_urls.txt")
    whitelist_path.unlink(missing_ok=True)

    tester = create_ai_tester()
    results = tester.call_ai_feedback()
    assert results["Test A"]["status"] == "error"
    assert "whitelist" in results["Test A"]["message"].lower()

    # Restore for other tests
    whitelist_path.write_text("https://polymouth.teach.cs.toronto.edu:443/chat\n")
