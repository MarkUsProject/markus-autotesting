import os
import stat
import tempfile

import pytest
from autotester.server.utils.file_management import setup_files

from pathlib import Path


@pytest.fixture
def t_path():
    """
    Returns a temporary directory with one sub directory
    """
    with tempfile.TemporaryDirectory() as tests_path:
        with tempfile.NamedTemporaryFile(dir=tests_path) as test_file:
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
        group_stfile = []
        group_scfile = []
        for fd, file_or_dir in student_files:
            group_stfile.append(Path(file_or_dir).group())
        for fd, file_or_dir in script_files:
            group_scfile.append(Path(file_or_dir).group())
        assert all(test_username == i for i in group_scfile)
        assert all(test_username == i for i in group_stfile)

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
        stdir_pmsn = []
        stfile_pmsn = []
        for fd, file_or_dir in student_files:
            if fd == "d":
                permission = fd_permission(file_or_dir)
                stdir_pmsn.append(
                    True
                ) if permission == "-rwxrwx---" else stdir_pmsn.append(False)
            else:
                permission = fd_permission(file_or_dir)
                stfile_pmsn.append(
                    True
                ) if permission == "-rw-rw----" else stfile_pmsn.append(False)
        assert all(i for i in stdir_pmsn)
        assert all(i for i in stfile_pmsn)

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
        scdir_pmsn = []
        scfile_pmsn = []
        for fd, file_or_dir in script_files:
            if fd == "d":
                permission = fd_permission(file_or_dir)
                scdir_pmsn.append(
                    True
                ) if permission == "drwxrwx--T" else scdir_pmsn.append(False)
            else:
                mode = os.stat(file_or_dir).st_mode
                permission = stat.filemode(mode)
                scfile_pmsn.append(
                    True
                ) if permission == "-rw-r-----" else scfile_pmsn.append(False)
        assert all(i for i in scdir_pmsn)
        assert all(i for i in scfile_pmsn)

    def test_copied_file(self, t_path, f_path, args):
        """
        Checks whether all the copied files are exists
        """
        markus_address, assignment_id = args
        tests_path = t_path
        files_path = f_path
        test_username = Path(tests_path).owner()
        student_files, script_files = setup_files(
            files_path, tests_path, test_username, markus_address, assignment_id
        )
        st_files = []
        scr_files = []
        [st_files.append(i[1]) for i in student_files]
        [scr_files.append(j[1]) for j in script_files]
        assert all(os.path.exists(f) for f in st_files)
        assert all(os.path.exists(f) for f in scr_files)
