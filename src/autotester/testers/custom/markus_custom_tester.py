import subprocess
from testers.markus_tester import MarkusTester
from testers.markus_test_specs import MarkusTestSpecs


class MarkusCustomTester(MarkusTester):
    def __init__(self, specs: MarkusTestSpecs) -> None:
        """ Initialize a MarkusCustomTester """
        super().__init__(specs, test_class=None)

    @MarkusTester.run_decorator
    def run(self) -> None:
        """
        Run a test and print the results to stdout
        """
        file_paths = self.specs["test_data", "script_files"]
        for file_path in file_paths:
            subprocess.run(f"./{file_path}")
