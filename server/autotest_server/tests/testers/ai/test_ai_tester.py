import subprocess
from ....testers.ai.ai_tester import AITester, AITest
from ....testers.specs import TestSpecs


def create_ai_tester(output="overall"):
    raw_spec = f"""
    {{
        "test_data": [
            {{
                "title": "Test A",
                "timeout": 30,
                "output": "{output}",
                "config": {{
                    "submission": "fixtures/sample_submission.R",
                    "model": "claude",
                    "scope": "code"
                }}
            }}
        ]
    }}
    """
    return AITester(specs=TestSpecs.from_json(raw_spec))


def test_ai_test_success_runs_properly():
    result = {"title": "Test A", "message": "Looks good", "status": "success"}
    test = AITest(tester=create_ai_tester(), result=result)
    output = test.run()
    assert '"status": "pass"' in output
    assert "Looks good" in output


def test_ai_test_error_runs_properly():
    result = {"title": "Test A", "message": "Syntax error", "status": "error"}
    test = AITest(tester=create_ai_tester(), result=result)
    output = test.run()
    assert '"status": "error"' in output
    assert "Syntax error" in output


def test_call_ai_feedback_success(monkeypatch):
    tester = create_ai_tester()

    mocked_result = subprocess.CompletedProcess(
        args=["python", "-m", "ai_feedback"], returncode=0, stdout="Great job!", stderr=""
    )

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: mocked_result)

    results = tester.call_ai_feedback()
    assert "Test A" in results
    assert results["Test A"]["status"] == "success"
    assert results["Test A"]["message"] == "Great job!"
    assert tester.overall_comments == ["Great job!"]
    assert tester.annotations == []


def test_call_ai_feedback_error(monkeypatch):
    tester = create_ai_tester()

    def raise_error(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args, stderr="Runtime error")

    monkeypatch.setattr(subprocess, "run", raise_error)

    results = tester.call_ai_feedback()
    assert results["Test A"]["status"] == "error"
    assert "Runtime error" in results["Test A"]["message"]
    assert tester.overall_comments == []
    assert tester.annotations == []


def test_run_prints_test_results(monkeypatch, capsys):
    tester = create_ai_tester()

    # Mock subprocess to simulate successful CLI call
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(args=a, returncode=0, stdout="Nice work", stderr=""),
    )

    # Replace AITest.run with a stub that returns a dummy string
    monkeypatch.setattr(AITest, "run", lambda self: '{"status": "success", "message": "Test Passed"}')

    tester.run()
    captured = capsys.readouterr()
    assert "Test Passed" in captured.out
