import json

from ....testers.specs import TestSpecs
from ....testers.js.js_tester import JsTester, JsTest


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
    tester = JsTester(
        specs=TestSpecs.from_json(
            '{"test_data": {"script_files": ["test.js"]}}'
        )
    )
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
    specs = TestSpecs.from_json(
        '{"test_data": {"script_files": ["test.js"]}, "points": {}}'
    )
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
    specs = TestSpecs.from_json(
        '{"test_data": {"script_files": ["test.js"]}, "points": {}}'
    )
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
