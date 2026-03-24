import json
import subprocess
from unittest.mock import MagicMock

from ....testers.specs import TestSpecs
from ....testers.js.js_tester import JsTester, JsTest


def make_tester():
    return JsTester(specs=TestSpecs.from_json('{"test_data": {"script_files": ["test.js"]}}'))


def make_jest_output(*test_dicts):
    """Build a minimal Jest JSON output containing the given assertion results."""
    return json.dumps({"testResults": [{"assertionResults": list(test_dicts)}]})


def test_parse_jest_output_returns_assertion_results():
    """Test that_parse_jest_output parses Jest JSON and returns assertionResults."""
    jest_json = {
        "testResults": [
            {
                "assertionResults": [
                    {
                        "fullName": "js test 1",
                        "status": "passed",
                        "failureMessages": [],
                    },
                    {
                        "fullName": "js test 2",
                        "status": "failed",
                        "failureMessages": ["Expected 1, got 2"],
                    },
                ]
            }
        ]
    }
    tester = make_tester()
    results, err = tester._parse_jest_output(json.dumps(jest_json))
    assert err is None
    assert len(results) == 2
    assert results[0]["fullName"] == "js test 1"
    assert results[0]["status"] == "passed"
    assert results[1]["fullName"] == "js test 2"
    assert results[1]["status"] == "failed"
    assert results[1]["failureMessages"] == ["Expected 1, got 2"]


def test_js_test_passed_output_format():
    """JsTest with status passed produces framework JSON with status pass."""
    specs = TestSpecs.from_json('{"test_data": {"script_files": ["test.js"]}, "points": {}}')
    tester = JsTester(specs=specs)
    result = {
        "fullName": "my test",
        "status": "passed",
        "failureMessages": [],
    }
    test = JsTest(tester, result)
    out = test.run()
    data = json.loads(out)
    assert data["name"] == "my test"
    assert data["status"] == "pass"
    assert data["marks_earned"] == data["marks_total"]
    assert data["marks_total"] == 1


def test_js_test_failed_output_format():
    """JsTest with status failed produces framework JSON with status fail."""
    specs = TestSpecs.from_json('{"test_data": {"script_files": ["test.js"]}, "points": {}}')
    tester = JsTester(specs=specs)
    result = {
        "fullName": "failing test",
        "status": "failed",
        "failureMessages": ["AssertionError: expected true"],
    }
    test = JsTest(tester, result)
    out = test.run()
    data = json.loads(out)
    assert data["name"] == "failing test"
    assert data["status"] == "fail"
    assert data["marks_earned"] == 0
    assert "expected true" in data["output"]


def test_parse_jest_output_invalid_json():
    """_parse_jest_output returns an error when given invalid JSON."""
    tester = make_tester()
    results, err = tester._parse_jest_output("not valid json")
    assert results is None
    assert err is not None


def test_pending_tests_are_skipped(monkeypatch, capsys):
    """JsTester.run() silently skips tests with status pending."""
    mock_pnpm = MagicMock()
    mock_pnpm.returncode = 0

    jest_output = make_jest_output(
        {"fullName": "skipped test", "status": "pending", "failureMessages": []},
    )
    mock_jest = MagicMock()
    mock_jest.stdout = jest_output
    mock_jest.returncode = 0

    def fake_run(cmd, **kwargs):
        if "pnpm" in cmd:
            return mock_pnpm
        return mock_jest

    monkeypatch.setattr(subprocess, "run", fake_run)
    tester = make_tester()
    tester.run()
    captured = capsys.readouterr()
    assert captured.out == ""


def test_run_prints_passed_and_failed_results(monkeypatch, capsys):
    """JsTester.run() prints output for each non-pending test."""
    mock_pnpm = MagicMock()
    mock_pnpm.returncode = 0

    jest_output = make_jest_output(
        {"fullName": "passing test", "status": "passed", "failureMessages": []},
        {"fullName": "failing test", "status": "failed", "failureMessages": ["oops"]},
    )
    mock_jest = MagicMock()
    mock_jest.stdout = jest_output
    mock_jest.returncode = 0

    def fake_run(cmd, **kwargs):
        if "pnpm" in cmd:
            return mock_pnpm
        return mock_jest

    monkeypatch.setattr(subprocess, "run", fake_run)
    tester = make_tester()
    tester.run()
    captured = capsys.readouterr()
    lines = [line for line in captured.out.strip().splitlines() if line]
    assert len(lines) == 2
    assert json.loads(lines[0])["status"] == "pass"
    assert json.loads(lines[1])["status"] == "fail"


def test_run_reports_failure_from_student_bug(monkeypatch, capsys):
    """JsTester.run() reports a failed test caused by student submission bug."""
    mock_pnpm = MagicMock()
    mock_pnpm.returncode = 0

    bug_message = "TypeError: Cannot read properties of undefined (reading 'length')"
    jest_output = make_jest_output(
        {"fullName": "student bug test", "status": "failed", "failureMessages": [bug_message]},
    )
    mock_jest = MagicMock()
    mock_jest.stdout = jest_output
    mock_jest.returncode = 0

    def fake_run(cmd, **kwargs):
        if "pnpm" in cmd:
            return mock_pnpm
        return mock_jest

    monkeypatch.setattr(subprocess, "run", fake_run)
    tester = make_tester()
    tester.run()
    out_line = capsys.readouterr().out.strip()
    data = json.loads(out_line)
    assert data["name"] == "student bug test"
    assert data["status"] == "fail"
    assert bug_message in data["output"]


def test_js_test_unexpected_status_returns_error_output():
    """JsTest returns an error result when Jest status is unexpected."""
    specs = TestSpecs.from_json('{"test_data": {"script_files": ["test.js"]}, "points": {}}')
    tester = JsTester(specs=specs)
    result = {
        "fullName": "runtime error test",
        "status": "error",
        "failureMessages": ["ReferenceError: x is not defined"],
    }
    test = JsTest(tester, result)
    out = test.run()
    data = json.loads(out)
    assert data["name"] == "runtime error test"
    assert data["status"] == "error"
    assert "ReferenceError" in data["output"]
