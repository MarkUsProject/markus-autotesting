from src.autotester.server.utils.file_management import *
import os.path
import re
import tempfile
import shutil
from src.autotester.config import config
FILES_DIRNAME = config["_workspace_contents", "_files_dir"]

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


def test_recursive_iglob():
    root_dir = tempfile.gettempdir()
    fd = list(recursive_iglob(root_dir))
    dir = []
    file = []
    for i in fd:
        dir.append(i[1]) if i[0] == "d" else file.append(i[1])
    assert all([os.path.isdir(d) for d in dir])
    assert all([os.path.isfile(f) for f in file])


def test_copy_tree():
    source_dir = tempfile.mkdtemp()
    fd, source_file = tempfile.mkstemp(dir=source_dir)
    dest_dir = tempfile.mkdtemp() 
    copy_tree(source_dir, dest_dir)
    copied_file = os.path.join(dest_dir, source_file)
    assert os.path.exists(copied_file)
    os.close(fd)
    shutil.rmtree(source_dir)
    shutil.rmtree(dest_dir)


def test_ignore_missing_dir_error():
    dir = tempfile.mkdtemp()
    shutil.rmtree(dir)
    error = True
    try:
        shutil.rmtree(dir, onerror=ignore_missing_dir_error)
    except:
        error = False
    assert error


def test_move_tree():
    source_dir = tempfile.mkdtemp()
    fd, source_file = tempfile.mkstemp(dir=source_dir)
    dest_dir = tempfile.mkdtemp()
    os.close(fd)
    move_tree(source_dir, dest_dir)
    file_name = os.path.basename(source_file)
    moved_file = os.path.join(dest_dir, file_name)
    assert os.path.exists(moved_file) and not os.path.exists(source_file)
    shutil.rmtree(dest_dir)


def test_fd_open():
    dir = tempfile.mkdtemp()
    dir_fd = os.open(dir, os.O_RDONLY)
    file_fd, file = tempfile.mkstemp(dir=dir)
    with fd_open(dir) as fdd:
        same_dir = os.path.sameopenfile(fdd, dir_fd)
    with fd_open(file) as fdf:
        same_file = os.path.sameopenfile(fdf, file_fd)
    assert same_dir and same_file
    assert type(fdd) is int
    assert type(fdf) is int
    os.close(dir_fd)
    os.close(file_fd)


def test_fd_lock():
    des, file = tempfile.mkstemp()
    access = True
    with fd_open(file) as fd:
        with fd_lock(fd):
            try:
                os.close(fd)
            except IOError as e:
                print(e)
                access = False
    print(access)
    assert not access

def test_copy_test_script_files():
    markus_address = "http://localhost:3000/csc108/en/main"
    assignment_id = 1
    tests_path = tempfile.mkdtemp()
    file_fd, test_file = tempfile.mkstemp(dir=dir)
    copy_test_script_files(markus_address, assignment_id, tests_path)
    test_script_outer_dir = redis_management.test_script_directory(
        markus_address, assignment_id
    )
    test_script_dir = os.path.join(test_script_outer_dir, FILES_DIRNAME)
    copied_file = os.path.join(test_script_dir, test_file)
    assert os.path.exists(copied_file)
    os.close(file_fd)
    shutil.rmtree(tests_path)