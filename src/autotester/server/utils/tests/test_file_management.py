import os
import stat
import tempfile

from autotester.server.utils.file_management import setup_files


def test_setup_files():
    markus_address = "http://localhost:3000/csc108/en/main"
    assignment_id = 1
    tests_path = tempfile.mkdtemp()
    file_fd, test_file = tempfile.mkstemp(dir=tests_path)
    files_path = tempfile.mkdtemp()
    f_d, files = tempfile.mkstemp(dir=files_path)
    student_files, script_files = setup_files(
        files_path, tests_path, markus_address, assignment_id
    )
    st_files = []
    scr_files = []
    [st_files.append(i[1]) for i in student_files]
    [scr_files.append(j[1]) for j in script_files]
    stdir_pmsn = []
    stfile_pmsn = []
    scdir_pmsn = []
    scfile_pmsn = []
    for fd, file_or_dir in student_files:
        if fd == "d":
            mode = os.stat(file_or_dir).st_mode
            permission = stat.filemode(mode)
            stdir_pmsn.append(
                True
            ) if permission == "-rwxrwx---" else stdir_pmsn.append(False)
        else:
            mode = os.stat(file_or_dir).st_mode
            permission = stat.filemode(mode)
            stfile_pmsn.append(
                True
            ) if permission == "-rw-rw----" else stfile_pmsn.append(False)
    for fd, file_or_dir in script_files:
        if fd == "d":
            mode = os.stat(file_or_dir).st_mode
            permission = stat.filemode(mode)
            scdir_pmsn.append(
                True
            ) if permission == "drwxrwx--T" else scdir_pmsn.append(False)
        else:
            mode = os.stat(file_or_dir).st_mode
            permission = stat.filemode(mode)
            scfile_pmsn.append(
                True
            ) if permission == "-rw-r-----" else scfile_pmsn.append(False)

    assert all([os.path.exists(f) for f in st_files])
    assert all([os.path.exists(f) for f in scr_files])
    assert all([i for i in stdir_pmsn])
    assert all([i for i in stfile_pmsn])
    assert all([i for i in scdir_pmsn])
    assert all([i for i in scfile_pmsn])
