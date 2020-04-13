from autotester.server.utils.path_management import current_directory, add_path
import tempfile
import os
import sys
import pytest

@pytest.fixture
def change_work_dir():
    temp_dir = tempfile.gettempdir()
    with current_directory(temp_dir):
        temp_work_dir = os.getcwd()
        yield temp_work_dir, temp_dir


class TestCurrentDirectory:
    def test_temp_work_dir(self, change_work_dir):
        """
        Checks whether the working directory is changed from current to temporary working directory
        """
        temp_work_dir, temp_dir = change_work_dir
        assert temp_work_dir == temp_dir

    def test_current_work_dir(self, change_work_dir):
        """
        Checks whether the working directory is changed from temporary to current working directory
        """
        curr_work_dir = os.getcwd()
        temp_work_dir, temp_dir = change_work_dir
        assert os.getcwd() == curr_work_dir


def test_add_path():
    """
    When adding the path which is not exist
    """
    path = tempfile.gettempdir()
    with add_path(path, prepend=True):
        prep = sys.path[0]
    with add_path(path, prepend=False):
        app = sys.path[-1]
    assert path == app == prep
    assert path not in sys.path


def test_add_existing_path():
    """
    When adding the path which exists already
    """
    sys_path = tempfile.gettempdir()
    sys.path.append(sys_path)
    with add_path(sys_path, prepend=True):
        prepend = sys.path[0]
    with add_path(sys_path, prepend=False):
        append = sys.path[-1]
    assert sys_path == append == prepend
    assert sys_path in sys.path
    sys.path.pop(-1)
