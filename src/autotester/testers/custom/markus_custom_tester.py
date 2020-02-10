import subprocess
from testers.markus_tester import MarkusTester


class MarkusCustomTester(MarkusTester):
    def __init__(self, specs):
        super().__init__(specs, test_class=None)

    @MarkusTester.run_decorator
    def run(self):
        file_paths = self.specs["test_data", "script_files"]
        for file_path in file_paths:
            subprocess.run(f"./{file_path}")
