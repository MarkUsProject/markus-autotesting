import json
import os
from pathlib import Path
from unittest.mock import patch

import subprocess
import pytest
from ....testers.ai.ai_tester import AiTester, AiTest
from ....testers.specs import TestSpecs

WHITELISTED_URL = "https://polymouth.teach.cs.toronto.edu:443/chat"


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
def mock_whitelist_config():
    """Mock server_config to return the whitelist from settings."""
    with patch("autotest_server.testers.ai.ai_tester.server_config") as mock_config:
        mock_config.get.side_effect = lambda key, default=None: (
            [WHITELISTED_URL] if key == "remote_url_whitelist" else default
        )
        yield mock_config


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
    tester = create_ai_tester(remote_url=WHITELISTED_URL)
    mocked = subprocess.CompletedProcess(
        args=["python", "-m", "ai_feedback"], returncode=0, stdout="Feedback", stderr=""
    )
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: mocked)
    results = tester.call_ai_feedback()
    assert results["Test A"]["status"] == "success"


def test_call_ai_feedback_empty_whitelist(mock_whitelist_config):
    """When no URLs are configured in settings, all remote URLs should be rejected."""
    mock_whitelist_config.get.side_effect = lambda key, default=None: (
        [] if key == "remote_url_whitelist" else default
    )
    tester = create_ai_tester()
    results = tester.call_ai_feedback()
    assert results["Test A"]["status"] == "error"
    assert "not whitelisted" in results["Test A"]["message"]
