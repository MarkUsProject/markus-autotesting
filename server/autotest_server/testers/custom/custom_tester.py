import subprocess
from ..tester import Tester
from ..specs import TestSpecs


class CustomTester(Tester):
    def __init__(self, specs: TestSpecs) -> None:
        """Initialize a CustomTester"""
        super().__init__(specs, test_class=None)

    @Tester.run_decorator
    def run(self) -> None:
        """
        Run a test and print the results to stdout
        """
        file_paths = self.specs["test_data", "script_files"]
        for file_path in file_paths:
            subprocess.run(f"./{file_path}")
