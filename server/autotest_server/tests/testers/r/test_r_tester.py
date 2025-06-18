import json
from unittest.mock import patch, MagicMock
from ....testers.specs import TestSpecs
from ....testers.r.r_tester import RTester, RTest


def test_success_with_context(request, monkeypatch):
    """Test that when R tests with context succeed, they are formatted correctly."""
    monkeypatch.chdir(request.fspath.dirname)

    # Mock R test results - simulates what R would return as JSON
    mock_r_output = [
        {
            "context": "Basic arithmetic",
            "test": "addition works correctly",
            "results": [{"type": "expectation_success", "message": ""}],
        }
    ]

    # Mock subprocess.run to return our simulated R output
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stdout = json.dumps(mock_r_output)
    mock_process.stderr = ""

    with patch("subprocess.run", return_value=mock_process):
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

        results = tester.run_r_tests()

        assert len(results) == 1
        assert "fixtures/sample_tests_success.R" in results
        test_results = results["fixtures/sample_tests_success.R"]
        assert len(test_results) > 0

        # Get the first result and create RTest to check formatting
        result = test_results[0]
        test = RTest(tester, "fixtures/sample_tests_success.R", result)

        # Test name formatting verification
        assert test.test_name.endswith("[fixtures/sample_tests_success.R] Basic arithmetic addition works correctly")
        assert test.test_name.startswith("[")
