from autotester.server.utils.file_management import (
    clean_dir_name,
    random_tmpfile_name,
    recursive_iglob,
    copy_tree,
    ignore_missing_dir_error,
    move_tree,
    copy_test_script_files,
    fd_open,
)
import os.path
import tempfile
import shutil
from autotester.config import config
import pytest
from fakeredis import FakeStrictRedis
from unittest.mock import patch


FILES_DIRNAME = config["_workspace_contents", "_files_dir"]
CURRENT_TEST_SCRIPT_HASH = config["redis", "_current_test_script_hash"]


@pytest.fixture
def empty_dir():
    """
    Yields an empty directory
    """
    with tempfile.TemporaryDirectory() as empty_directory:
        yield empty_directory


@pytest.fixture
def dir_has_onefile():
    """
    Yields a directory which has only one file
    """
    with tempfile.TemporaryDirectory() as dir:
        with tempfile.NamedTemporaryFile(dir=dir) as file:
            yield dir, file.name


@pytest.fixture
def dir_has_onedir():
    """
    Yields a directory with one sub directory
    """
    with tempfile.TemporaryDirectory() as dir:
        with tempfile.TemporaryDirectory(dir=dir) as sub_dir:
            yield dir, sub_dir


@pytest.fixture
def nested_fd():
    """
    Yields a nested file structure
    """
    with tempfile.TemporaryDirectory() as root_dir:
        with tempfile.TemporaryDirectory(dir=root_dir) as sub_dir1:
            with tempfile.TemporaryDirectory(dir=sub_dir1) as sub_dir2:
                with tempfile.NamedTemporaryFile(dir=sub_dir2) as file:
                    yield root_dir, sub_dir1, sub_dir2, file.name


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
def empty_tmp_script_dir():
    """
    Mock the test_script_directory method and yield an empty temporary directory
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        files_dir = os.path.join(tmp_dir, "files")
        os.mkdir(files_dir)
        with patch(
            "autotester.server.utils.redis_management.test_script_directory",
            return_value=tmp_dir,
        ):
            yield tmp_dir


@pytest.fixture
def tmp_script_dir_with_onefile():
    """
    Mock the test_script_directory method and yield a temporary directory and a file
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        files_dir = os.path.join(tmp_dir, "files")
        os.mkdir(files_dir)
        with tempfile.NamedTemporaryFile(dir=files_dir) as file:
            with patch(
                "autotester.server.utils.redis_management.test_script_directory",
                return_value=tmp_dir,
            ):
                yield tmp_dir, file.name


@pytest.fixture
def tmp_script_dir_with_onedir():
    """
    Mock the test_script_directory method and yield a temporary directory and a sub directory
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        files_dir = os.path.join(tmp_dir, "files")
        os.mkdir(files_dir)
        with tempfile.TemporaryDirectory(dir=files_dir) as sub_sir:
            with patch(
                "autotester.server.utils.redis_management.test_script_directory",
                return_value=tmp_dir,
            ):
                yield tmp_dir, sub_sir


@pytest.fixture
def nested_tmp_script_dir():
    """
    Mock the test_script_directory method and yield a temporary directory and nested file structure
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        files_dir = os.path.join(tmp_dir, "files")
        os.mkdir(files_dir)
        with tempfile.TemporaryDirectory(dir=files_dir) as sub_dir1:
            with tempfile.TemporaryDirectory(dir=sub_dir1) as sub_dir2:
                with tempfile.NamedTemporaryFile(dir=sub_dir2) as file:
                    with patch(
                        "autotester.server.utils.redis_management.test_script_directory",
                        return_value=tmp_dir,
                    ):
                        yield tmp_dir, sub_dir1, sub_dir2, file.name


def list_of_fd(file_or_dir):
    """
    Gets a list of files and directories and returns two separate list for files and directories
    """
    dir = []
    files = []
    for i in file_or_dir:
        dir.append(i[1]) if i[0] == "d" else files.append(i[1])
    return dir, files


def test_clean_dir_name():
    """
    Checks whether '/' is replaced by '_' for a given path
    """
    a = "markus/address"
    b = a.replace("/", "_")
    assert clean_dir_name(a) == b


def test_random_tmpfile_name():
    """
    Checks the temporary file name is random
    """
    tmp_file_1 = random_tmpfile_name()
    tmp_file_2 = random_tmpfile_name()
    assert not tmp_file_1 == tmp_file_2


class TestRecursiveIglob:
    """
    Checks that all the files and directories of a given path are listed
    """

    def test_empty_dir(self, empty_dir):
        """
        When the Directory is empty
        """
        file_or_dir = list(recursive_iglob(empty_dir))
        dir, files = list_of_fd(file_or_dir)
        assert not dir and not files

    def test_dir_has_onefile(self, dir_has_onefile):
        """
        When the Directory has only one file
        """
        root_dir, file = dir_has_onefile
        file_or_dir = list(recursive_iglob(root_dir))
        dir, files = list_of_fd(file_or_dir)
        assert not dir
        assert len(files) == 1 and file in files
        assert os.path.exists(files[0])

    def test_dir_has_onedir(self, dir_has_onedir):
        """
        When the Directory has only one sub directory
        """
        root_dir, sub_dir = dir_has_onedir
        file_or_dir = list(recursive_iglob(root_dir))
        dir, files = list_of_fd(file_or_dir)
        assert not files
        assert len(dir) == 1 and sub_dir in dir
        assert os.path.exists(dir[0])

    def test_dir_has_nestedfd(self, nested_fd):
        """
        When the files are nested in subdirectories more than 2 directories deep
        """
        root_dir, sub_dir1, sub_dir2, file = nested_fd
        file_or_dir = list(recursive_iglob(root_dir))
        dir, files = list_of_fd(file_or_dir)
        assert all(os.path.exists(d) for d in dir)
        assert all(os.path.exists(f) for f in files)
        assert sub_dir1 in dir and sub_dir2 in dir
        assert file in files


class TestCopyTree:
    """
    Checks that all the contents are copied from source to destination
    """

    def test_empty_dir(self, empty_dir, dir_has_onefile):
        """
        When the Source Directory is empty
        """
        source_dir = empty_dir
        dest_dir, file = dir_has_onefile
        list_fd_bef_copy = os.listdir(dest_dir)
        copy_tree(source_dir, dest_dir)
        list_fd_after_copy = os.listdir(dest_dir)
        assert len(list_fd_bef_copy) == len(list_fd_after_copy)

    def test_dir_has_onefile(self, dir_has_onefile, empty_dir):
        """
        When the Source Directory has only one file
        """
        source_dir, source_file = dir_has_onefile
        dest_dir = empty_dir
        copy_tree(source_dir, dest_dir)
        copied_file = os.path.join(dest_dir, os.path.basename(source_file))
        assert os.path.exists(copied_file)

    def test_dir_has_onedir(self, dir_has_onedir, empty_dir):
        """
        When the Source Directory has only one sub directory
        """
        source_dir, sub_dir = dir_has_onedir
        dest_dir = empty_dir
        copy_tree(source_dir, dest_dir)
        copied_dir = os.path.join(dest_dir, os.path.basename(sub_dir))
        assert os.path.exists(copied_dir)

    def test_dir_has_nestedfd(self, empty_dir, nested_fd):
        """
        When the files are nested in subdirectories more than 2 directories deep
        """
        dest_dir = empty_dir
        source_dir, sub_dir1, sub_dir2, source_file = nested_fd
        copy_tree(source_dir, dest_dir)
        copied_dir1 = os.path.join(dest_dir, os.path.basename(sub_dir1))
        copied_dir2 = os.path.join(copied_dir1, os.path.basename(sub_dir2))
        copied_file = os.path.join(copied_dir2, os.path.basename(source_file))
        assert os.path.exists(copied_dir1)
        assert os.path.exists(copied_dir2)
        assert os.path.exists(copied_file)


def test_ignore_missing_dir_error():
    """
    Checks whether the missing directory error is ignored
    when we try to remove a directory which is not exist
    """
    dir = tempfile.mkdtemp()
    shutil.rmtree(dir)
    shutil.rmtree(dir, onerror=ignore_missing_dir_error)


class TestMoveTree:
    """
    Checks that all the contents are moved from source to destination
    """

    def test_empty_dir(self, empty_dir, dir_has_onedir):
        """
        When the Source Directory is empty
        """
        source_dir = tempfile.mkdtemp()
        dest_dir, sub_dir = dir_has_onedir
        list_fd_bef_move = os.listdir(dest_dir)
        move_tree(source_dir, dest_dir)
        list_fd_after_move = os.listdir(dest_dir)
        assert len(list_fd_bef_move) == len(list_fd_after_move)

    def test_dir_has_onefile(self, empty_dir):
        """
        When the Source Directory has only one file
        """
        source_dir = tempfile.mkdtemp()
        fd, source_file = tempfile.mkstemp(dir=source_dir)
        dest_dir = empty_dir
        move_tree(source_dir, dest_dir)
        moved_file = os.path.join(dest_dir, os.path.basename(source_file))
        assert os.path.exists(moved_file) and not os.path.exists(source_file)

    def test_dir_has_onedir(self, empty_dir, dir_has_onedir):
        """
        When the Dirctory has only one sub directory
        """
        source_dir = tempfile.mkdtemp()
        sub_dir = tempfile.mkdtemp(dir=source_dir)
        dest_dir = empty_dir
        move_tree(source_dir, dest_dir)
        moved_dir = os.path.join(dest_dir, os.path.basename(sub_dir))
        assert os.path.exists(moved_dir) and not os.path.exists(sub_dir)

    def test_dir_has_nestedfd(self, empty_dir, nested_fd):
        """
        When the files are nested in subdirectories more than 2 directories deep
        """
        dest_dir = empty_dir
        source_dir = tempfile.mkdtemp()
        sub_dir1 = tempfile.mkdtemp(dir=source_dir)
        sub_dir2 = tempfile.mkdtemp(dir=sub_dir1)
        fd, source_file = tempfile.mkstemp(dir=sub_dir2)
        move_tree(source_dir, dest_dir)
        moved_dir1 = os.path.join(dest_dir, os.path.basename(sub_dir1))
        moved_dir2 = os.path.join(moved_dir1, os.path.basename(sub_dir2))
        moved_file = os.path.join(moved_dir2, os.path.basename(source_file))
        assert os.path.exists(moved_dir1) and not os.path.exists(sub_dir1)
        assert os.path.exists(moved_dir2)
        assert os.path.exists(moved_file)


class TestFdOpen:
    def test_open_dir(self):
        """
        Checks whether two file descriptors are pointing to the same directory
        """
        with tempfile.TemporaryDirectory() as dir:
            dir_fd = os.open(dir, os.O_RDONLY)
            with fd_open(dir) as fdd:
                same_dir = os.path.sameopenfile(fdd, dir_fd)
            assert same_dir

    def test_open_file(self):
        """
        Checks whether two file descriptors are pointing to the same file
        """
        with tempfile.NamedTemporaryFile() as file:
            file_fd = os.open(file.name, os.O_RDONLY)
            with fd_open(file.name) as fdf:
                same_file = os.path.sameopenfile(fdf, file_fd)
            assert same_file

    def test_close(self):
        """
        Checks whether the file or directory is closed
        """
        with tempfile.TemporaryDirectory() as dir:
            with fd_open(dir) as fdd:
                dir_fd = fdd
            with pytest.raises(Exception):
                os.close(dir_fd)


class TestCopyTestScriptFiles:
    """
    Checks whether all the test script directory contents are copied into tests_path
    """

    def test_empty_dir(self, dir_has_onefile):
        """
        When the test script directory is empty has only one file
        """
        markus_address = "http://localhost:3000/csc108/en/main"
        assignment_id = 1
        tests_path, test_file = dir_has_onefile
        list_fd_bef_copy = os.listdir(tests_path)
        copy_test_script_files(markus_address, assignment_id, tests_path)
        list_fd_after_copy = os.listdir(tests_path)
        assert len(list_fd_bef_copy) == len(list_fd_after_copy)

    def test_dir_has_onefile(self, dir_has_onefile, tmp_script_dir_with_onefile):
        """
        When the test script directory has only one file
        """
        markus_address = "http://localhost:3000/csc108/en/main"
        assignment_id = 1
        tests_path, test_file = dir_has_onefile
        tmp_script_dir, file = tmp_script_dir_with_onefile
        copy_test_script_files(markus_address, assignment_id, tests_path)
        copied_file = os.path.join(tests_path, file)
        assert os.path.exists(copied_file)

    def test_dir_has_onedir(self, dir_has_onefile, tmp_script_dir_with_onedir):
        """
        When the test script directory has only one sub directory
        """
        markus_address = "http://localhost:3000/csc108/en/main"
        assignment_id = 1
        tests_path, test_file = dir_has_onefile
        tmp_script_dir, sub_dir = tmp_script_dir_with_onedir
        copy_test_script_files(markus_address, assignment_id, tests_path)
        copied_dir = os.path.join(tests_path, sub_dir)
        assert os.path.exists(copied_dir)

    def test_dir_has_nested_fd(self, dir_has_onefile, nested_tmp_script_dir):
        """
        When the files are nested in subdirectories more than 2 directories deep
        """
        markus_address = "http://localhost:3000/csc108/en/main"
        assignment_id = 1
        tests_path, test_file = dir_has_onefile
        tmp_script_dir, sub_dir1, sub_dir2, file = nested_tmp_script_dir
        copy_test_script_files(markus_address, assignment_id, tests_path)
        copied_dir1 = os.path.join(tests_path, os.path.basename(sub_dir1))
        copied_dir2 = os.path.join(copied_dir1, os.path.basename(sub_dir2))
        copied_file = os.path.join(copied_dir2, os.path.basename(file))
        assert os.path.exists(copied_dir1)
        assert os.path.exists(copied_dir2)
        assert os.path.exists(copied_file)
