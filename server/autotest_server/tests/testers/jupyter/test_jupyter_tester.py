from ....testers.specs import TestSpecs
from ....testers.jupyter.jupyter_tester import JupyterTest, JupyterTester


def test_jupyter_test_name_format_direct():
    """Directly test the test_name format of JupyterTest."""

    test_file_path = "notebooks/test_example.ipynb"
    result = {
        "status": "success",
        "name": "some.module::TestNotebook.test_case_one",
        "errors": "",
        "description": None,
    }

    class DummyTester(JupyterTester):
        def __init__(self):
            super().__init__(specs=TestSpecs())

        def run(self):
            pass

    test = JupyterTest(
        tester=DummyTester(),
        test_file=test_file_path,
        test_file_name=test_file_path,
        result=result,
    )

    expected_name = "[notebooks/test_example.ipynb] TestNotebook.test_case_one"
    assert test.test_name == expected_name
