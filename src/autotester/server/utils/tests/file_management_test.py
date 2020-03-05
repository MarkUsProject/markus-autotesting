import os.path
import re
import tempfile
from src.autotester.server.utils.file_management import *


def test_clean_dir_name():
    a = 'markus/address'
    b = a.replace('/', '_')
    assert clean_dir_name(a) == b


def test_random_tmpfile_name():
    tmp_file = random_tmpfile_name()
    dir_name = os.path.dirname(tmp_file)
    base_name = os.path.basename(tmp_file)
    assert os.path.exists(dir_name) and re.match(r'[+\-]''0''[xX]''0|''([1-9A-Fa-f][1-9A-Fa-f]*)', base_name)


def test_recursive_iglob():
    root_dir = tempfile.gettempdir()
    fd = list(recursive_iglob(root_dir))
    dir = []
    file = []
    for i in fd:
        dir.append(i[1]) if i[0] == 'd' else file.append(i[1])
    assert all([os.path.isdir(d) for d in dir])
    assert all([os.path.isfile(f) for f in file])
