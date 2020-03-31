from autotester.server.utils.file_management import (
    clean_dir_name,
    random_tmpfile_name,
    recursive_iglob,
    copy_tree,
    copy_test_script_files,
    ignore_missing_dir_error,
    move_tree,
    fd_open,
    fd_lock,
)
from autotester.server.utils import redis_management
import os.path
import re
import tempfile
import shutil
from autotester.config import config
import subprocess
import pytest

FILES_DIRNAME = config["_workspace_contents", "_files_dir"]

@pytest.fixture
def input1():
    dir1 = tempfile.mkdtemp()
    fd, file1 = tempfile.mkstemp(dir=dir1)
    dir2 = tempfile.mkdtemp()
    sub_dir = tempfile.mkdtemp(dir=dir2)
    dir3 = tempfile.mkdtemp()
    sub_dir1 = tempfile.mkdtemp(dir=dir3)
    sub_dir2 = tempfile.mkdtemp(dir=sub_dir1)
    fd, file3 = tempfile.mkstemp(dir=sub_dir2)
    yield dir1, file1, dir2, sub_dir, dir3, sub_dir1, sub_dir2, file3
    if os.path.exists(dir1): shutil.rmtree(dir1)
    if os.path.exists(dir2): shutil.rmtree(dir2)
    if os.path.exists(dir3): shutil.rmtree(dir3)


def list_of_fd(file_or_dir):
    dir = []
    files = []
    for i in file_or_dir:
        dir.append(i[1]) if i[0] == "d" else files.append(i[1])
    return dir, files


def test_clean_dir_name():
    a = "markus/address"
    b = a.replace("/", "_")
    assert clean_dir_name(a) == b


def test_random_tmpfile_name():
    tmp_file = random_tmpfile_name()
    dir_name = os.path.dirname(tmp_file)
    base_name = os.path.basename(tmp_file)
    assert os.path.exists(dir_name) and re.match(
        r"[+\-]" "0" "[xX]" "0|" "([1-9A-Fa-f][1-9A-Fa-f]*)", base_name
    )


# When the Directory is empty
def test_recursive_iglob_1(input1):
    _,_,_,empty_dir, *_ = input1
    file_or_dir = list(recursive_iglob(empty_dir))
    dir, files = list_of_fd(file_or_dir)
    assert not dir and not files


# When the Directory has only one file
def test_recursive_iglob_2(input1):
    root_dir, file, *_ = input1
    file_or_dir = list(recursive_iglob(root_dir))
    dir, files = list_of_fd(file_or_dir)
    assert not dir
    assert len(files) == 1 and file in files
    assert os.path.exists(files[0])


# When the Dirctory has only one sub directory
def test_recursive_iglob_3(input1):
    _,_, root_dir, sub_dir, *_ = input1
    file_or_dir = list(recursive_iglob(root_dir))
    dir, files = list_of_fd(file_or_dir)
    assert not files
    assert len(dir) == 1 and sub_dir in dir
    assert os.path.exists(dir[0])


# When the files are nested in subdirectories more than 2 directories deep
def test_recursive_iglob_4(input1):
    *_, root_dir, sub_dir1, sub_dir2, file = input1
    file_or_dir = list(recursive_iglob(root_dir))
    dir, files = list_of_fd(file_or_dir)
    assert all(os.path.exists(d) for d in dir)
    assert all(os.path.exists(f) for f in files)
    assert sub_dir1 in dir and sub_dir2 in dir
    assert file in files


# When the Source Directory is empty
def test_copy_tree_1(input1):
    dest_dir, _, _, source_dir, *_ = input1
    list_fd_bef_copy = os.listdir(dest_dir)
    copy_tree(source_dir, dest_dir)
    list_fd_after_copy = os.listdir(dest_dir)
    assert len(list_fd_bef_copy) == len(list_fd_after_copy)


# When the Source Directory has only one file
def test_copy_tree_2(input1):
    source_dir, source_file, _, dest_dir, *_ = input1
    copy_tree(source_dir, dest_dir)
    copied_file = os.path.join(dest_dir, os.path.basename(source_file))
    assert os.path.exists(copied_file)


# When the Dirctory has only one sub directory
def test_copy_tree_3(input1):
    dest_dir, _, source_dir, sub_dir, *_ = input1
    copy_tree(source_dir, dest_dir)
    copied_dir = os.path.join(dest_dir, os.path.basename(sub_dir))
    assert os.path.exists(copied_dir)


# When the files are nested in subdirectories more than 2 directories deep
def test_copy_tree_4(input1):
    _, _, dest_dir, _, source_dir, sub_dir1, sub_dir2, source_file = input1
    copy_tree(source_dir, dest_dir)
    copied_dir1 = os.path.join(dest_dir, os.path.basename(sub_dir1))
    copied_dir2 = os.path.join(copied_dir1, os.path.basename(sub_dir2))
    copied_file = os.path.join(copied_dir2, os.path.basename(source_file))
    assert os.path.exists(copied_dir1)
    assert os.path.exists(copied_dir2)
    assert os.path.exists(copied_file)


def test_ignore_missing_dir_error():
    dir = tempfile.mkdtemp()
    shutil.rmtree(dir)
    error = True
    try:
        shutil.rmtree(dir, onerror=ignore_missing_dir_error)
    except FileNotFoundError:
        error = False
    assert error


# When the Source Directory is empty
def test_move_tree_1(input1):
    dest_dir, _, _, source_dir, *_ = input1
    list_fd_bef_move = os.listdir(dest_dir)
    move_tree(source_dir, dest_dir)
    list_fd_after_move = os.listdir(dest_dir)
    assert len(list_fd_bef_move) == len(list_fd_after_move)


# When the Source Directory has only one file
def test_move_tree_2(input1):
    source_dir, source_file, _, dest_dir, *_ = input1
    move_tree(source_dir, dest_dir)
    moved_file = os.path.join(dest_dir, os.path.basename(source_file))
    assert os.path.exists(moved_file) and not os.path.exists(source_file)


# When the Dirctory has only one sub directory
def test_move_tree_3(input1):
    dest_dir, _, source_dir, sub_dir, *_ = input1
    move_tree(source_dir, dest_dir)
    moved_dir = os.path.join(dest_dir, os.path.basename(sub_dir))
    assert os.path.exists(moved_dir) and not os.path.exists(sub_dir)


# When the files are nested in subdirectories more than 2 directories deep
def test_move_tree_4(input1):
    _, _, dest_dir, _, source_dir, sub_dir1, sub_dir2, source_file = input1
    move_tree(source_dir, dest_dir)
    moved_dir1 = os.path.join(dest_dir, os.path.basename(sub_dir1))
    moved_dir2 = os.path.join(moved_dir1, os.path.basename(sub_dir2))
    moved_file = os.path.join(moved_dir2, os.path.basename(source_file))
    assert os.path.exists(moved_dir1) and not os.path.exists(sub_dir1)
    assert os.path.exists(moved_dir2)
    assert os.path.exists(moved_file)


def test_fd_open():
    dir = tempfile.mkdtemp()
    dir_fd = os.open(dir, os.O_RDONLY)
    file_fd, file = tempfile.mkstemp(dir=dir)
    with fd_open(dir) as fdd:
        same_dir = os.path.sameopenfile(fdd, dir_fd)
    with fd_open(file) as fdf:
        same_file = os.path.sameopenfile(fdf, file_fd)
    assert same_dir and same_file
    os.close(dir_fd)
    os.close(file_fd)


def test_fd_lock(input1):
    temp_dir, temp_file, *_ = input1
    access = True
    with fd_open(temp_dir) as fd:
        with fd_lock(fd):
            try:
                subprocess.run(["rm", {temp_file}])
            except Exception:
                access = False
    assert not access


def test_copy_test_script_files(input1):
    markus_address = "http://localhost:3000/csc108/en/main"
    assignment_id = 1
    tests_path, test_file, *_ = input1
    copy_test_script_files(markus_address, assignment_id, tests_path)
    test_script_outer_dir = redis_management.test_script_directory(
        markus_address, assignment_id
    )
    test_script_dir = os.path.join(test_script_outer_dir, FILES_DIRNAME)
    copied_file = os.path.join(test_script_dir, test_file)
    assert os.path.exists(copied_file)
