from ....testers.specs import TestSpecs
from ....testers.py.py_tester import PyTester, PyTest
import json
import re


def test_success(request, monkeypatch) -> None:
    """Test that when a test succeeds, it is added to the results."""
    monkeypatch.chdir(request.fspath.dirname)
    tester = PyTester(specs=TestSpecs.from_json("""
        {
          "test_data": {
            "script_files": ["fixtures/sample_tests_success.py"],
            "category": ["instructor"],
            "timeout": 30,
            "tester": "pytest",
            "output_verbosity": "short",
            "extra_info": {
              "criterion": "",
              "name": "Python Test Group 1"
            }
          }
        }
    """))
    results = tester.run_python_tests()
    assert len(results) == 1
    assert "fixtures/sample_tests_success.py" in results
    assert len(results["fixtures/sample_tests_success.py"]) == 1

    result = results["fixtures/sample_tests_success.py"][0]
    assert result["status"] == "success"
    # nodeid is inexact in CI test
    assert re.search(r"\[.*sample_tests_success\.py\] test_add_one$", result["name"])
    assert result["errors"] == ""
    assert result["description"] is None


def test_skip(request, monkeypatch) -> None:
    """Test that when a test is skipped, it is omitted from the results."""
    monkeypatch.chdir(request.fspath.dirname)
    tester = PyTester(specs=TestSpecs.from_json("""
        {
          "test_data": {
            "script_files": ["fixtures/sample_tests_skip.py"],
            "category": ["instructor"],
            "timeout": 30,
            "tester": "pytest",
            "output_verbosity": "short",
            "extra_info": {
              "criterion": "",
              "name": "Python Test Group 1"
            }
          }
        }
    """))
    results = tester.run_python_tests()
    assert results == {"fixtures/sample_tests_skip.py": []}


def test_marks_earned_respected_when_equal_to_total(request, monkeypatch) -> None:
    """Test that markus_marks_earned is respected even when earned == total and test fails (TICKET-602)."""
    monkeypatch.chdir(request.fspath.dirname)
    tester = PyTester(specs=TestSpecs.from_json("""
        {
          "test_data": {
            "script_files": ["fixtures/sample_tests_marks_earned.py"],
            "category": ["instructor"],
            "timeout": 30,
            "tester": "pytest",
            "output_verbosity": "short",
            "extra_info": {
              "criterion": "",
              "name": "Python Test Group 1"
            }
          }
        }
    """))
    results = tester.run_python_tests()
    test_results = results["fixtures/sample_tests_marks_earned.py"]
    assert len(test_results) == 3

    # Build PyTest instances and run them to get final marks
    outputs = []
    for res in test_results:
        test = PyTest(tester, "fixtures/sample_tests_marks_earned.py", res)
        outputs.append(json.loads(test.run()))

    assert len(outputs) == 3

    # Sort by marks_earned so assertions are deterministic
    outputs.sort(key=lambda o: o["marks_earned"])

    # marks_earned=0: should get 0 marks (TICKET-603)
    assert outputs[0]["marks_earned"] == 0
    assert outputs[0]["marks_total"] == 2

    # marks_earned=1: should get 1 mark (partial)
    assert outputs[1]["marks_earned"] == 1
    assert outputs[1]["marks_total"] == 2

    # marks_earned=2: should get 2 marks, not 0 (TICKET-602)
    assert outputs[2]["marks_earned"] == 2
    assert outputs[2]["marks_total"] == 2
