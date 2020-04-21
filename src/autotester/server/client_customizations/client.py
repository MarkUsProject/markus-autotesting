from abc import ABC, abstractmethod
from typing import Dict


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

    @abstractmethod
    def upload_feedback_to_repo(self, feedback_file: str) -> None:
        """
        Upload a feedback file to a client's repository
        TODO: deprecate and get rid of this option
        """
        pass

    @abstractmethod
    def upload_feedback_file(self, feedback_file: str) -> None:
        """ Upload a feedback file to the client """
        pass

    @abstractmethod
    def upload_annotations(self, annotation_file: str) -> None:
        """ Upload a feedback file to a client's repository """
        pass
