import os
import stat
import tempfile

import pytest
from fakeredis import FakeStrictRedis
from unittest.mock import patch
from autotester.config import config
from autotester.server.utils.file_management import setup_files

from pathlib import Path

FILES_DIRNAME = config["_workspace_contents", "_files_dir"]


@pytest.fixture(autouse=True)
def redis():
    """
    Mock the redis connection with fake redis and yield the fake redis
    """
    fake_redis = FakeStrictRedis()
    with patch(
        "autotester.server.utils.redis_management.redis_connection",
        return_value=fake_redis,
    ):
        yield fake_redis


@pytest.fixture(autouse=True)
def tmp_script_dir():
    """
    Mock the test_script_directory method and yield a temporary directory
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        files_dir = os.path.join(tmp_dir, FILES_DIRNAME)
        os.mkdir(files_dir)
        with tempfile.NamedTemporaryFile(dir=files_dir):
            with patch(
                "autotester.server.utils.redis_management.test_script_directory",
                return_value=tmp_dir,
            ):
                yield tmp_dir


@pytest.fixture
def t_path():
    """
    Returns a temporary directory with one sub directory
    """
    with tempfile.TemporaryDirectory() as tests_path:
        with tempfile.NamedTemporaryFile(dir=tests_path):
            yield tests_path


@pytest.fixture
def f_path():
    """
    Returns a temporary directory with one sub directory
    """
    files_path = tempfile.mkdtemp()
    f_d, files = tempfile.mkstemp(dir=files_path)
    return files_path


@pytest.fixture
def args():
    """
    Returns markus address and assignment id
    """
    markus_address = "http://localhost:3000/csc108/en/main"
    assignment_id = 1
    return markus_address, assignment_id


def fd_permission(file_or_dir):
    """
    Gets file or directory and returns its permission
    """
    mode = os.stat(file_or_dir).st_mode
    permission = stat.filemode(mode)
    return permission


class TestSetupFiles:
    def test_group_owner(self, t_path, f_path, args):
        """
        Checks whether the group owner of both
        student files and script files changed into test_username
        """
        markus_address, assignment_id = args
        tests_path = t_path
        files_path = f_path
        test_username = Path(tests_path).owner()
        student_files, script_files = setup_files(
            files_path, tests_path, test_username, markus_address, assignment_id
        )
        for _fd, file_or_dir in student_files:
            assert test_username == Path(file_or_dir).group()
        for _fd, file_or_dir in script_files:
            assert test_username == Path(file_or_dir).group()

    def test_student_files(self, t_path, f_path, args):
        """
        Checks whether the permission of files and directories
        in student files changed into '0o770' and '0o660'
        """
        markus_address, assignment_id = args
        tests_path = t_path
        files_path = f_path
        test_username = Path(tests_path).owner()
        student_files, script_files = setup_files(
            files_path, tests_path, test_username, markus_address, assignment_id
        )
        for fd, file_or_dir in student_files:
            if fd == "d":
                assert fd_permission(file_or_dir) == "-rwxrwx---"
            else:
                assert fd_permission(file_or_dir) == "-rw-rw----"

    def test_script_files(self, t_path, f_path, args):
        """
        Checks whether the permission of files and directories
        in script files changed into '0o1770' and '0o640'
        """
        markus_address, assignment_id = args
        tests_path = t_path
        files_path = f_path
        test_username = Path(tests_path).owner()
        student_files, script_files = setup_files(
            files_path, tests_path, test_username, markus_address, assignment_id
        )
        for fd, file_or_dir in script_files:
            if fd == "d":
                assert fd_permission(file_or_dir) == "drwxrwx--T"
            else:
                assert fd_permission(file_or_dir) == "-rw-r-----"

    def test_copied_file(self, t_path, f_path, args):
        """
        Checks whether all the copied files are exists.
        student_files:
        All the contents from files_path are moved into tests_path
        and the moved contents are returned here as student_files.
        script_files:
        All the contents from the test_script_directory of
        corresponding markus_address and assignment_id are copied
        into tests_path and the copied contents are returned here as script_files.
        """
        markus_address, assignment_id = args
        tests_path = t_path
        files_path = f_path
        test_username = Path(tests_path).owner()
        student_files, script_files = setup_files(
            files_path, tests_path, test_username, markus_address, assignment_id
        )
        for _fd, file_or_dir in student_files:
            assert os.path.exists(file_or_dir)
        for _fd, file_or_dir in script_files:
            assert os.path.exists(file_or_dir)
