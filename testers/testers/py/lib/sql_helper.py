from psycopg2 import connect as _unmockable_psycopg2_connect
import os
from unittest.mock import patch
from contextlib import contextmanager
import subprocess


def _in_autotest_env():
    """
    Checks if we are running in an autotesting environment.

    An autotesting environment is one where db connection
    environment variables are set by the autotester
    """
    return os.environ.get('AUTOTESTENV') == 'true'


def _connection(*args, **kwargs):
    """
    Return a connection to a database used by the autotester if the environment
    variables AUTOTEST_DATABASE and AUTOTEST_PWD are set. Otherwise return a
    connection to a database determined by the args and kwargs passed to this
    function.
    """
    if _in_autotest_env:
        database = os.environ.get('PGDATABASE')
        password = os.environ.get('PGPASSWORD')
        user = os.environ.get('PGUSER')
        return _unmockable_psycopg2_connect(database=database, user=user, password=password)
    return _unmockable_psycopg2_connect(*args, **kwargs)


@contextmanager
def mock_connect(target='psycopg2.connect'):
    """
    Context manager that mocks any call to the function decribed in the <target> string
    with the connection function (in this module).

    See the documentation for unittest.mock.patch for a description of the format of the
    <target> string.

    By default, the function that will be mocked is the function called as psycopg2.connect

    If you import this function differently then you should change the <target> argument to
    match:

        from psycopg2 import connect  -> target='__main__.connect'
        from pyscopg2 import connect as conn -> target='__main__.conn'

    This can be used as a context manager:

    with mock_connect():
        ... something ...
        psycopg2.connect(*args, **kwargs) # <- this will call connection instead

    This can also be used as a decorator for a function:

    @mock_connect()
    def f():
        ... something ...
        psycopg2.connect(*args, **kwargs) # <- this will call connection instead
    """
    with patch(target, side_effect=_connection, autospec=True):
        yield


def execute_file(filename, *args, database=None, password=None, user=None):
    """
    Executes a sql file <filename> by passing it as the argument to the -f flag when
    executing the psql command. Returns a subprocess.CompletedProcess object from which
    the caller can inspect the stdout, stderr, returncode, etc. arguments.

    If not calling this function in an autotesting environment (see _in_autotest_env), you
    should call this with the database kwarg and optionally the password and user kwargs if
    necessary to connect to your database. If running in an autotesting environment, these
    kwargs will be ignored in favour of the environment variables set by the autotester.

    Additional <args> will be added to the call to the psql command. Do not include args
    for the '-d', '-f', '-u', '-w', '-W' flags or the call may not run as expected.
    """
    if _in_autotest_env():
        env = os.environ
    else:
        db_vars = {
            'PGUSER': user or os.environ.get('PGUSER'),
            'PGPASSWORD': password or os.environ.get('PGPASSWORD'),
            'PGDATABASE': database or os.environ.get('PGDATABASE')
        }
        env = {**os.environ, **db_vars}
    return subprocess.run(['psql', '-f', filename] + args, env=env, capture_output=True)
