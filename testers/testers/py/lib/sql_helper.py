import psycopg2
import os

def connection(*args, **kwargs):
    """
    Return a connection to a database used by the autotester if the environment
    variables AUTOTEST_DATABASE and AUTOTEST_PWD are set. Otherwise return a 
    connection to a database determined by the args and kwargs passed to this
    function.
    """
    database = os.environ.get('AUTOTEST_DATABASE')
    password = os.environ.get('AUTOTEST_PWD')
    if database is not None and password is not None:
        return psycopg2.connection(database=database, user=database, password=password)
    return psycopg2.connection(*args, **kwargs)
