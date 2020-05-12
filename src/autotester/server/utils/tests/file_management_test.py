from autotester.server.utils.file_management import (
    clean_dir_name,
    random_tmpfile_name,
    recursive_iglob,
    copy_tree,
    ignore_missing_dir_error,
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
    empty_dir = tempfile.TemporaryDirectory()
    yield empty_dir.name
    if os.path.exists(empty_dir.name):
        empty_dir.cleanup()


@pytest.fixture
def dir_has_one_file():
    """
    Yields a directory which has only one file
    """
    tmp_dir = tempfile.TemporaryDirectory()
    tmp_file = tempfile.NamedTemporaryFile(dir=tmp_dir.name)
    yield tmp_dir.name, tmp_file.name
    if os.path.exists(tmp_dir.name):
        tmp_dir.cleanup()


@pytest.fixture
def dir_has_one_dir():
    """
    Yields a directory with one subdirectory
    """
    tmp_dir = tempfile.TemporaryDirectory()
    sub_dir = tempfile.TemporaryDirectory(dir=tmp_dir.name)
    yield tmp_dir.name, sub_dir.name
    if os.path.exists(tmp_dir.name):
        tmp_dir.cleanup()


@pytest.fixture
def dir_has_multiple_fd():
    """
    Yields a directory which has multiple files and directories
    """
    root_dir = tempfile.TemporaryDirectory()
    dir1 = tempfile.TemporaryDirectory(dir=root_dir.name)
    file1 = tempfile.NamedTemporaryFile(dir=root_dir.name)
    tempfile.TemporaryDirectory(dir=root_dir.name)
    tempfile.NamedTemporaryFile(dir=root_dir.name)
    yield root_dir.name, dir1.name, file1.name
    if os.path.exists(root_dir.name):
        root_dir.cleanup()


@pytest.fixture
def nested_fd():
    """
    Yields a nested file structure
    """
    root_dir = tempfile.TemporaryDirectory()
    sub_dir1 = tempfile.TemporaryDirectory(dir=root_dir.name)
    sub_dir2 = tempfile.TemporaryDirectory(dir=sub_dir1.name)
    file = tempfile.NamedTemporaryFile(dir=sub_dir2.name)
    yield root_dir.name, sub_dir1.name, sub_dir2.name, file.name
    if os.path.exists(root_dir.name):
        root_dir.cleanup()


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


@pytest.fixture
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


def list_of_fd(file_or_dir):
    """
    Gets a list of files and directories and returns two separate lists for files and directories
    """
    dirs = []
    files = []
    for i in file_or_dir:
        dirs.append(i[1]) if i[0] == "d" else files.append(i[1])
    return dirs, files


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
        When the directory is empty
        """
        dirs, files = list_of_fd(recursive_iglob(empty_dir))
        assert not dirs and not files

    def test_dir_has_one_file(self, dir_has_one_file):
        """
        When the directory has only one file
        """
        root_dir, file = dir_has_one_file
        dirs, files = list_of_fd(recursive_iglob(root_dir))
        assert not dirs
        assert len(files) == 1 and file in files
        assert all(os.path.exists(f) for f in files)

    def test_dir_has_one_dir(self, dir_has_one_dir):
        """
        When the directory has only one subdirectory
        """
        root_dir, sub_dir = dir_has_one_dir
        dirs, files = list_of_fd(recursive_iglob(root_dir))
        assert not files
        assert len(dirs) == 1 and sub_dir in dirs
        assert all(os.path.exists(d) for d in dirs)

    def test_dir_has_nested_fd(self, nested_fd):
        """
        When the files are nested in subdirectories more than 2 directories deep
        """
        root_dir, sub_dir1, sub_dir2, file = nested_fd
        dirs, files = list_of_fd(recursive_iglob(root_dir))
        assert all(os.path.exists(d) for d in dirs)
        assert all(os.path.exists(f) for f in files)
        assert sub_dir1 in dirs and sub_dir2 in dirs
        assert file in files


class TestCopyTree:
    """
    Checks that all the contents are copied from source to destination
    """

    def test_empty_dir(self, empty_dir, dir_has_one_file):
        """
        When the source directory is empty and the destination directory is not empty
        """
        source_dir = empty_dir
        dest_dir, file = dir_has_one_file
        list_fd_before_copy = os.listdir(dest_dir)
        copied_file_or_dir = copy_tree(source_dir, dest_dir)
        list_fd_after_copy = os.listdir(dest_dir)
        assert len(list_fd_before_copy) == len(list_fd_after_copy)
        assert not copied_file_or_dir

    def test_dir_has_one_file(self, dir_has_one_file, empty_dir):
        """
        When the source directory has only one file
        """
        source_dir, source_file = dir_has_one_file
        dest_dir = empty_dir
        copied_file_or_dir = copy_tree(source_dir, dest_dir)
        for _fd, file_or_dir in copied_file_or_dir:
            assert os.path.exists(file_or_dir)

    def test_dir_has_one_dir(self, dir_has_one_dir, empty_dir):
        """
        When the source directory has only one subdirectory
        """
        source_dir, sub_dir = dir_has_one_dir
        dest_dir = empty_dir
        copied_file_or_dir = copy_tree(source_dir, dest_dir)
        for _fd, file_or_dir in copied_file_or_dir:
            assert os.path.exists(file_or_dir)

    def test_dir_has_nested_fd(self, empty_dir, nested_fd):
        """
        When the files are nested in subdirectories more than 2 directories deep
        """
        dest_dir = empty_dir
        source_dir, sub_dir1, sub_dir2, source_file = nested_fd
        copied_file_or_dir = copy_tree(source_dir, dest_dir)
        for _fd, file_or_dir in copied_file_or_dir:
            assert os.path.exists(file_or_dir)

    def test_dir_has_multiple_fd(self, empty_dir, dir_has_multiple_fd):
        """
        When the source directory has more than one file or directory
        """
        dest_dir = empty_dir
        source_dir, *_ = dir_has_multiple_fd
        copied_file_or_dir = copy_tree(source_dir, dest_dir)
        for _fd, file_or_dir in copied_file_or_dir:
            assert os.path.exists(file_or_dir)

    def test_exclude(self, empty_dir, dir_has_multiple_fd):
        """
        Checks whether the files or directories in the exclude list are not copied
        """
        dest_dir = empty_dir
        source_dir, sub_dir, source_file = dir_has_multiple_fd
        sub_dir_name = os.path.basename(sub_dir)
        source_file_name = os.path.basename(source_file)
        copied_file_or_dir = copy_tree(
            source_dir, dest_dir, exclude=(sub_dir_name, source_file_name)
        )
        for _fd, file_or_dir in copied_file_or_dir:
            assert os.path.exists(file_or_dir)
        excluded_dir = os.path.join(dest_dir, sub_dir_name)
        excluded_file = os.path.join(dest_dir, source_file_name)
        assert not os.path.exists(excluded_dir)
        assert not os.path.exists(excluded_file)


def test_ignore_missing_dir_error():
    """
    Checks whether the missing directory error is ignored
    when we try to remove a directory which is not exist
    """
    tmp_dir = tempfile.mkdtemp()
    shutil.rmtree(tmp_dir)
    shutil.rmtree(tmp_dir, onerror=ignore_missing_dir_error)


class TestFdOpen:
    def test_open_dir(self):
        """
        Checks whether two file descriptors are pointing to the same directory
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            dir_fd = os.open(tmp_dir, os.O_RDONLY)
            with fd_open(tmp_dir) as fdd:
                assert os.path.sameopenfile(fdd, dir_fd)

    def test_open_file(self):
        """
        Checks whether two file descriptors are pointing to the same file
        """
        with tempfile.NamedTemporaryFile() as file:
            file_fd = os.open(file.name, os.O_RDONLY)
            with fd_open(file.name) as fdf:
                assert os.path.sameopenfile(fdf, file_fd)

    def test_close(self):
        """
        Checks whether the file or directory is closed
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            with fd_open(tmp_dir) as fdd:
                dir_fd = fdd
            with pytest.raises(IOError):
                os.close(dir_fd)
