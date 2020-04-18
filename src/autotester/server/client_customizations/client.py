from abc import ABC, abstractmethod


class Client(ABC):
    @abstractmethod
    def write_test_files(self, destination: str) -> None:
        pass

    @abstractmethod
    def get_test_specs(self) -> None:
        pass

    @abstractmethod
    def write_student_files(self, destination: str) -> None:
        pass

    @abstractmethod
    def send_test_results(self, results) -> None:
        pass

    @abstractmethod
    def unique_script_str(self) -> str:
        pass

    @abstractmethod
    def unique_run_str(self) -> str:
        pass

    def upload_feedback_to_repo(self, feedback_file: str) -> None:
        pass

    def upload_feedback_file(self, feedback_file: str) -> None:
        pass

    def upload_annotations(self, annotation_file: str) -> None:
        pass
