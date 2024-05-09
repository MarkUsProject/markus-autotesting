from ....testers.specs import TestSpecs
from ....testers.py.py_tester import PyTester


def test_success(request, monkeypatch) -> None:
    """Test that when a test succeeds, it is added to the results."""
    monkeypatch.chdir(request.fspath.dirname)
    tester = PyTester(
        specs=TestSpecs.from_json(
            """
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
    """
        )
    )
    results = tester.run_python_tests()
    assert len(results) == 1
    assert "fixtures/sample_tests_success.py" in results
    assert len(results["fixtures/sample_tests_success.py"]) == 1

    result = results["fixtures/sample_tests_success.py"][0]
    assert result["status"] == "success"
    # nodeid is inexact in CI test
    assert result["name"].endswith("fixtures/sample_tests_success.py::test_add_one")
    assert result["errors"] == ""
    assert result["description"] is None


def test_skip(request, monkeypatch) -> None:
    """Test that when a test is skipped, it is omitted from the results."""
    monkeypatch.chdir(request.fspath.dirname)
    tester = PyTester(
        specs=TestSpecs.from_json(
            """
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
    """
        )
    )
    results = tester.run_python_tests()
    assert results == {"fixtures/sample_tests_skip.py": []}
