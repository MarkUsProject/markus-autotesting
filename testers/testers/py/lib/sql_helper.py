import psycopg2
import os
import getpass

def connection(*args, **kwargs):
    """
    Return a connection to a database used by the autotester if the environment
    variables AUTOTEST_DATABASE and AUTOTEST_PWD are set. Otherwise return a
    connection to a database determined by the args and kwargs passed to this
    function.
    """
    database = os.environ.get('AUTOTEST_DATABASE')
    password = os.environ.get('AUTOTEST_PWD')
    user = getpass.getuser()

    if database is None or password is None:
        return psycopg2.connect(*args, **kwargs)
    return psycopg2.connect(database=database, user=user, password=password)
