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
    assert test.test_name.startswith("[")
