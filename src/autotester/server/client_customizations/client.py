from abc import ABC, abstractmethod
from typing import Dict, Callable
from functools import wraps


class Client(ABC):
    @abstractmethod
    def write_test_files(self, destination: str) -> None:
        """ Get test files from the client and write them to <destination> """
        pass

    @abstractmethod
    def get_test_specs(self) -> Dict:
        """ Get and Return test specs from the client """
        pass

    @abstractmethod
    def write_student_files(self, destination: str) -> None:
        """ Get student files from the client and write them to <destination> """
        pass

    @abstractmethod
    def send_test_results(self, results) -> None:
        """ Send test results to the client """
        pass

    @abstractmethod
    def unique_script_str(self) -> str:
        """ Return a unique string to represent the test scripts used to run tests """
        pass

    @abstractmethod
    def unique_run_str(self) -> str:
        """ Return a unique string to represent an individual run of tests """
        pass

    @staticmethod
    def _return_error_str(f: Callable) -> Callable:
        @wraps(f)
        def return_error_str(*args, **kwargs):
            try:
                f(*args, **kwargs)
            except Exception as e:
                return str(e)
            return ""

        return return_error_str

    @abstractmethod
    def after_test(self, test_data: Dict, cwd: str) -> str:
        """
        Run after each test where test_data is the data for the test and cwd the directory where the test is run.
        Return any error messages.
        """
        pass
