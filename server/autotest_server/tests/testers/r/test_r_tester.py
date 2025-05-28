from ....testers.specs import TestSpecs
from ....testers.r.r_tester import RTester, RTest


def test_success_with_context(request, monkeypatch):
    """Test that when R tests with context succeed, they are formatted correctly."""
    monkeypatch.chdir(request.fspath.dirname)
    tester = RTester(
        specs=TestSpecs.from_json(
            """
        {
          "test_data": {
            "script_files": ["fixtures/sample_tests_success.R"],
            "category": ["instructor"],
            "timeout": 30,
            "extra_info": {
              "criterion": "",
              "name": "R Test Group 1"
            }
          }
        }
    """
        )
    )

    # Run the actual R tests
    results = tester.run_r_tests()

    # Check basic structure
    assert len(results) == 1
    assert "fixtures/sample_tests_success.R" in results

    # Check that we have test results
    test_results = results["fixtures/sample_tests_success.R"]
    assert len(test_results) > 0

    # Get the first result and create RTest to check formatting
    result = test_results[0]
    test = RTest(tester, "fixtures/sample_tests_success.R", result)

    # nodeid is inexact in CI test
    assert test.test_name.endswith("[fixtures/sample_tests_success.R] Basic arithmetic addition works correctly")
    assert test.test_name.startswith("[")  # Uses brackets


def test_success_without_context(request, monkeypatch):
    """Test that when R tests without context succeed, they are formatted correctly."""
    monkeypatch.chdir(request.fspath.dirname)
    tester = RTester(
        specs=TestSpecs.from_json(
            """
        {
          "test_data": {
            "script_files": ["fixtures/sample_tests_no_context.R"],
            "category": ["instructor"],
            "timeout": 30,
            "extra_info": {
              "criterion": "",
              "name": "R Test Group 2"
            }
          }
        }
    """
        )
    )

    # Run the actual R tests
    results = tester.run_r_tests()

    # Check basic structure
    assert len(results) == 1
    assert "fixtures/sample_tests_no_context.R" in results

    # Check test formatting without context
    test_results = results["fixtures/sample_tests_no_context.R"]
    assert len(test_results) > 0

    # Get the first result and create RTest to check formatting
    result = test_results[0]
    test = RTest(tester, "fixtures/sample_tests_no_context.R", result)

    # nodeid is inexact in CI test
    assert test.test_name.endswith("[fixtures/sample_tests_no_context.R] multiplication works")

    # Verify formatting for tests without context
    assert test.test_name.startswith("[")  # Uses brackets


def test_failure_formatting(request, monkeypatch):
    """Test that failing R tests are still formatted correctly."""
    monkeypatch.chdir(request.fspath.dirname)
    tester = RTester(
        specs=TestSpecs.from_json(
            """
        {
          "test_data": {
            "script_files": ["fixtures/sample_tests_failure.R"],
            "category": ["instructor"],
            "timeout": 30,
            "extra_info": {
              "criterion": "",
              "name": "R Test Group 3"
            }
          }
        }
    """
        )
    )

    # Run the actual R tests (they will fail but should still format correctly)
    results = tester.run_r_tests()

    # Check basic structure
    assert len(results) == 1
    assert "fixtures/sample_tests_failure.R" in results

    # Check test formatting even for failures
    test_results = results["fixtures/sample_tests_failure.R"]
    assert len(test_results) > 0

    # Get the first result and create RTest to check formatting
    result = test_results[0]
    test = RTest(tester, "fixtures/sample_tests_failure.R", result)

    # nodeid is inexact in CI test
    assert test.test_name.endswith("[fixtures/sample_tests_failure.R] String operations division fails correctly")

    assert test.test_name.startswith("[")  # Uses brackets
