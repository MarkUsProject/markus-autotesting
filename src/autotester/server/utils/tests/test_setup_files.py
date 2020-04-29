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


@pytest.fixture
def empty_tmp_script_dir():
    """
    Mock the test_script_directory method and yield an empty temporary directory
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        files_dir = os.path.join(tmp_dir, FILES_DIRNAME)
        os.mkdir(files_dir)
        with patch(
            "autotester.server.utils.redis_management.test_script_directory",
            return_value=tmp_dir,
        ):
            yield tmp_dir


@pytest.fixture
def tmp_script_outer_dir():
    """
    Mock the test_script_directory method and yield a temporary directory
    which has no subdirectory from FILES_DIRNAME but has other file or directory
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tempfile.NamedTemporaryFile(dir=tmp_dir)
        tempfile.TemporaryDirectory(dir=tmp_dir)
        with patch(
            "autotester.server.utils.redis_management.test_script_directory",
            return_value=tmp_dir,
        ):
            yield tmp_dir


@pytest.fixture(autouse=True)
def tmp_script_dir_with_one_file():
    """
    Mock the test_script_directory method and yield a temporary directory which has only one file
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        files_dir = os.path.join(tmp_dir, FILES_DIRNAME)
        os.mkdir(files_dir)
        tempfile.NamedTemporaryFile(dir=files_dir)
        with patch(
            "autotester.server.utils.redis_management.test_script_directory",
            return_value=tmp_dir,
        ):
            yield tmp_dir


@pytest.fixture
def tmp_script_dir_with_one_dir():
    """
    Mock the test_script_directory method and yield a temporary directory which has only one subdirectory
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        files_dir = os.path.join(tmp_dir, FILES_DIRNAME)
        os.mkdir(files_dir)
        tempfile.TemporaryDirectory(dir=files_dir)
        with patch(
            "autotester.server.utils.redis_management.test_script_directory",
            return_value=tmp_dir,
        ):
            yield tmp_dir


@pytest.fixture
def nested_tmp_script_dir():
    """
    Mock the test_script_directory method and yield a temporary directory which has nested file structure
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        files_dir = os.path.join(tmp_dir, FILES_DIRNAME)
        os.mkdir(files_dir)
        with tempfile.TemporaryDirectory(dir=files_dir) as sub_dir1:
            with tempfile.TemporaryDirectory(dir=sub_dir1) as sub_dir2:
                tempfile.NamedTemporaryFile(dir=sub_dir2)
                with patch(
                    "autotester.server.utils.redis_management.test_script_directory",
                    return_value=tmp_dir,
                ):
                    yield tmp_dir


@pytest.fixture
def tmp_script_dir_has_multiple_fd():
    """
    Mock the test_script_directory method and yield a temporary directory
    which has more than one file or directory
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        files_dir = os.path.join(tmp_dir, FILES_DIRNAME)
        os.mkdir(files_dir)
        tempfile.TemporaryDirectory(dir=files_dir)
        tempfile.NamedTemporaryFile(dir=files_dir)
        with tempfile.TemporaryDirectory(dir=files_dir) as root_dir:
            with tempfile.TemporaryDirectory(dir=root_dir) as sub_dir:
                tempfile.NamedTemporaryFile(dir=sub_dir)
                with patch(
                    "autotester.server.utils.redis_management.test_script_directory",
                    return_value=tmp_dir,
                ):
                    yield tmp_dir


@pytest.fixture
def tests_path():
    """
    Returns a temporary directory which has only one file
    """
    with tempfile.TemporaryDirectory() as tests_path:
        with tempfile.NamedTemporaryFile(dir=tests_path):
            yield tests_path


@pytest.fixture
def f_path_empty():
    """
    Returns an empty temporary directory
    """
    files_path = tempfile.TemporaryDirectory()
    yield files_path.name
    if os.path.exists(files_path.name):
        files_path.cleanup()


@pytest.fixture
def f_path_has_one_file():
    """
    Returns a temporary directory which has only one file
    """
    files_path = tempfile.TemporaryDirectory()
    tempfile.NamedTemporaryFile(dir=files_path.name)
    yield files_path.name
    if os.path.exists(files_path.name):
        files_path.cleanup()


@pytest.fixture
def f_path_has_one_dir():
    """
    Returns a temporary directory which has only one subdirectory
    """
    files_path = tempfile.TemporaryDirectory()
    tempfile.TemporaryDirectory(dir=files_path.name)
    yield files_path.name
    if os.path.exists(files_path.name):
        files_path.cleanup()


@pytest.fixture
def f_path_has_multiple_fd():
    """
    Returns a temporary directory which has more than one file and directory
    """
    files_path = tempfile.TemporaryDirectory()
    tempfile.TemporaryDirectory(dir=files_path.name)
    tempfile.TemporaryDirectory(dir=files_path.name)
    tempfile.NamedTemporaryFile(dir=files_path.name)
    tempfile.NamedTemporaryFile(dir=files_path.name)
    yield files_path.name
    if os.path.exists(files_path.name):
        files_path.cleanup()


@pytest.fixture
def f_path_has_nested_fd():
    """
    Returns a temporary directory which has nested file structure
    """
    files_path = tempfile.TemporaryDirectory()
    sub_dir1 = tempfile.TemporaryDirectory(dir=files_path.name)
    sub_dir2 = tempfile.TemporaryDirectory(dir=sub_dir1.name)
    tempfile.NamedTemporaryFile(dir=sub_dir2.name)
    tempfile.NamedTemporaryFile(dir=sub_dir2.name)
    yield files_path.name
    if os.path.exists(files_path.name):
        files_path.cleanup()


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
    """
    student_files:
        All the contents from files_path are moved into tests_path
        and the moved contents are returned here as student_files.
    script_files:
        All the contents from the test_script_directory of
        corresponding markus_address and assignment_id are copied
        into tests_path and the copied contents are returned here as script_files.
    Checks whether all the copied files are exists.
    Checks the permission of files and directories in student_files and script_files
    """

    def test_group_owner(
        self, tests_path, f_path_has_one_file, args, tmp_script_dir_with_one_file
    ):
        """
        Checks whether the group owner of both
        student files and script files changed into test_username
        """
        markus_address, assignment_id = args
        files_path = f_path_has_one_file
        test_username = Path(tests_path).owner()
        student_files, script_files = setup_files(
            files_path, tests_path, test_username, markus_address, assignment_id
        )
        for _fd, file_or_dir in student_files:
            assert test_username == Path(file_or_dir).group()
        for _fd, file_or_dir in script_files:
            assert test_username == Path(file_or_dir).group()

    def test_student_files(
        self, tests_path, f_path_has_one_file, args, tmp_script_dir_with_one_file
    ):
        """
        Checks whether the permission of files and directories
        in student files changed into '0o770' and '0o660'
        """
        markus_address, assignment_id = args
        files_path = f_path_has_one_file
        test_username = Path(tests_path).owner()
        student_files, script_files = setup_files(
            files_path, tests_path, test_username, markus_address, assignment_id
        )
        for fd, file_or_dir in student_files:
            if fd == "d":
                assert fd_permission(file_or_dir) == "-rwxrwx---"
            else:
                assert fd_permission(file_or_dir) == "-rw-rw----"

    def test_script_files(
        self, tests_path, f_path_has_one_file, args, tmp_script_dir_with_one_file
    ):
        """
        Checks whether the permission of files and directories
        in script files changed into '0o1770' and '0o640'
        """
        markus_address, assignment_id = args
        files_path = f_path_has_one_file
        test_username = Path(tests_path).owner()
        student_files, script_files = setup_files(
            files_path, tests_path, test_username, markus_address, assignment_id
        )
        for fd, file_or_dir in script_files:
            if fd == "d":
                assert fd_permission(file_or_dir) == "drwxrwx--T"
            else:
                assert fd_permission(file_or_dir) == "-rw-r-----"

    def test_f_path_empty(self, tests_path, f_path_empty, args, empty_tmp_script_dir):
        """

        """
        markus_address, assignment_id = args
        files_path = f_path_empty
        test_username = Path(tests_path).owner()
        student_files, script_files = setup_files(
            files_path, tests_path, test_username, markus_address, assignment_id
        )
        assert not student_files
        assert not script_files

    def test_f_path_has_one_file(self, tests_path, f_path_has_one_file, args):
        """
        When the files_path and the test_script_dir has only one file
        """
        markus_address, assignment_id = args
        files_path = f_path_has_one_file
        test_username = Path(tests_path).owner()
        student_files, script_files = setup_files(
            files_path, tests_path, test_username, markus_address, assignment_id
        )
        for _fd, file_or_dir in student_files:
            assert os.path.exists(file_or_dir)
        for _fd, file_or_dir in script_files:
            assert os.path.exists(file_or_dir)

    def test_f_path_has_one_dir(
        self, tests_path, f_path_has_one_dir, args, tmp_script_dir_with_one_dir
    ):
        """
        When the files_path and the test_script_dir has only one directory
        """
        markus_address, assignment_id = args
        files_path = f_path_has_one_dir
        test_username = Path(tests_path).owner()
        student_files, script_files = setup_files(
            files_path, tests_path, test_username, markus_address, assignment_id
        )
        for _fd, file_or_dir in student_files:
            assert os.path.exists(file_or_dir)
        for _fd, file_or_dir in script_files:
            assert os.path.exists(file_or_dir)

    def test_f_path_has_multiple_fd(
        self, tests_path, f_path_has_multiple_fd, args, tmp_script_dir_has_multiple_fd
    ):
        """
        When the files_path and the test_script_dir has multiple files and directories
        """
        markus_address, assignment_id = args
        files_path = f_path_has_multiple_fd
        test_username = Path(tests_path).owner()
        student_files, script_files = setup_files(
            files_path, tests_path, test_username, markus_address, assignment_id
        )
        for _fd, file_or_dir in student_files:
            assert os.path.exists(file_or_dir)
        for _fd, file_or_dir in script_files:
            assert os.path.exists(file_or_dir)

    def test_f_path_has_nested_fd(
        self, tests_path, f_path_has_nested_fd, args, nested_tmp_script_dir
    ):
        """
        When the files_path and the test_script_dir has only one file
        """
        markus_address, assignment_id = args
        files_path = f_path_has_nested_fd
        test_username = Path(tests_path).owner()
        student_files, script_files = setup_files(
            files_path, tests_path, test_username, markus_address, assignment_id
        )
        for _fd, file_or_dir in student_files:
            assert os.path.exists(file_or_dir)
        for _fd, file_or_dir in script_files:
            assert os.path.exists(file_or_dir)

    def test_dir_has_no_files_dir(
        self, tests_path, f_path_has_one_file, args, tmp_script_outer_dir
    ):
        """
        When test_script_dir has no subdirectory from FILES_DIRNAME but has other file or directory
        """
        markus_address, assignment_id = args
        files_path = f_path_has_one_file
        test_username = Path(tests_path).owner()
        student_files, script_files = setup_files(
            files_path, tests_path, test_username, markus_address, assignment_id
        )
        for _fd, file_or_dir in student_files:
            assert os.path.exists(file_or_dir)
        assert not script_files
