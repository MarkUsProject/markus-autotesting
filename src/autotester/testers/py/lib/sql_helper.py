import os
import inspect
import subprocess
from unittest.mock import patch
from contextlib import contextmanager
from typing import ContextManager, Callable, Optional, List, ClassVar, Type
from psycopg2.extensions import AsIs
from psycopg2.extensions import cursor as _psycopg2_cursor
from psycopg2.extensions import connection as _psycopg2_connection
from psycopg2 import connect as _unmockable_psycopg2_connect

CursorType = Type[_psycopg2_cursor]
ConnectionType = Type[_psycopg2_connection]


def _in_autotest_env() -> bool:
    """
    Return true iff this script is being run by the MarkUs autotester.

    This function can be used to check whether the AUTOTESTENV environment
    variable has been set to 'true'.
    """
    return os.environ.get("AUTOTESTENV") == "true"


def connection(*args, **kwargs):
    """
    Return a psycopg2 connection object

    If this function is called while being run by the MarkUs autotester,
    any arguments passed to this function will be ignored and a connection will
    be made to the correct database in the autotester's run environment.

    If this function is called elsewhere, the arguments passed to this function
    will be used to call psycopg2.connect in order to connect to a database.
    """
    if _in_autotest_env():
        kwargs = {
            **kwargs,
            "database": os.environ.get("PGDATABASE"),
            "password": os.environ.get("PGPASSWORD"),
            "user": os.environ.get("PGUSER"),
            "host": "localhost",
        }
    return _unmockable_psycopg2_connect(*args, **kwargs)


@contextmanager
def patch_connection(target: str = "psycopg2.connect") -> ContextManager:
    """
    Context manager that patches any call to the function decribed in the
    <target> string with the connection function (in this module).

    See the documentation for unittest.mock.patch for a description of the
    format of the <target> string. By default, the function that will be
    mocked is the function called as psycopg2.connect. This function can
    also be used as a function decorator.

    >>> import psycopg2
    >>> with patch_connection():
    >>>     conn = psycopg2.connect()

    >>> from psycopg2 import connect
    >>> with patch_connection('__main__.connect'):
    >>>     conn = connect() # calls __main__._connection instead

    >>> import psycopg2
    >>> @patch_connection()
    >>> def f():
    >>>     conn = psycopg2.connect() # calls __main__._connection instead
    """
    with patch(target, side_effect=connection):
        yield


def patch_connection_class(target: str = "psycopg2.connect") -> Callable:
    """
    Class decorator that adds the patch_connection decorator to every method
    in the class.

    The <target> argument is passed to each patch_connection decorator.

    >>> @patch_connection_class()
    >>> class C:
    >>>     def __init__(self):
    >>>         self.conn = psycopg2.connect() # calls __main__._connection instead
    """

    def _connect(cls):
        for name, method in inspect.getmembers(cls, inspect.isroutine):
            setattr(cls, name, patch_connection(target)(method))
        return cls

    return _connect


def execute_psql_file(
    filename: str,
    *args: str,
    database: Optional[str] = None,
    password: Optional[str] = None,
    user: Optional[str] = None
) -> subprocess.CompletedProcess:
    """
    Return a CompletedProcess object returned after calling:

        $ psql -f <filename> [<args>]

    If this function is called while being run by the MarkUs autotester,
    the <database>, <password> and <user> arguments function will be ignored
    and a connection will be made to the correct database in the autotester's
    run environment instead.

    This function should be used when the file to execute contains psql
    commands or uses the COPY function. Otherwise using the psycopg2's execute
    function on the file contents directly will work and will give more
    accessible results.

    == precondition ==

    Addition arguments in <args> should not include arguments for the following
    flags: '-d', '-f', '-u', '-w', '-W'
    (see documentation for the psql command for details)

    >>> with open('my_file.sql', 'w') as f: f.write('\\list')
    >>> proc = execute_file('my_file.sql')
    >>> len(proc.stdout) > 0
    True

    >>> with open('my_file.sql', 'w') as f:
    >>>     f.write("COPY (SELECT * from table) TO 'tmp.out';")
    >>> proc = execute_file('my_file.sql')
    >>> with open('tmp.out') as f: len(f.read()) > 1
    True
    """
    if _in_autotest_env():
        env = os.environ
    else:
        db_vars = {
            "PGUSER": user or os.environ.get("PGUSER"),
            "PGPASSWORD": password or os.environ.get("PGPASSWORD"),
            "PGDATABASE": database or os.environ.get("PGDATABASE"),
        }
        env = {**os.environ, **db_vars}
    return subprocess.run(["psql", "-f", filename] + list(args), env=env, capture_output=True)


class PSQLTest:

    connection: ClassVar[Optional[ConnectionType]] = None

    SCHEMA_COPY_STR = """
    CREATE TABLE %(new)s.%(table)s (
        LIKE %(old)s.%(table)s INCLUDING ALL
    );
    INSERT INTO %(new)s.%(table)s
        SELECT * FROM %(old)s.%(table)s;
    """

    GET_TABLES_STR = """SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = %s;
    """

    @classmethod
    def create_connection(cls, *args, **kwargs) -> None:
        """
        Set an open connection to a database as a class attribute.

        If this function is called while being run by the MarkUs autotester,
        any arguments passed to this function will be ignored and a connection
        will be made to the correct database in the autotester's run
        environment.

        If this function is called elsewhere, the arguments passed to this
        function will be used to call psycopg2.connect in order to connect to a
        database.
        """
        cls.connection = connection(*args, **kwargs)

    @classmethod
    def close_connection(cls) -> None:
        """
        Closes the connection created by calling create_connection.

        The create_connection method must be called first or there will be no
        connection to close.
        """
        cls.connection.close()

    @classmethod
    @contextmanager
    def cursor(cls, *args, **kwargs) -> ContextManager[CursorType]:
        """
        Context manager that yields a cursor object from the connection
        created by calling create_connection.

        The arguments passed to this method are passed on to the cursor's
        constructor. The create_connection method must be called first or
        there will be no connection to create a cursor object on.
        """
        with cls.connection as conn:
            with conn.cursor(*args, **kwargs) as curr:
                yield curr

    @classmethod
    @contextmanager
    def schema(cls, schema: str, persist: bool = False) -> ContextManager:
        """
        Context manager that creates a schema named <schema> and sets the
        search path to that schema.

        After the context manager exits, the search path is set back to the
        previous schema and the newly created schema is dropped unless
        <persist> is True.
        """
        with cls.cursor() as curr:
            curr.execute("SHOW SEARCH_PATH;")
            org_search_path = [AsIs(path) for path in curr.fetchall()[0]]
            curr.execute("CREATE SCHEMA IF NOT EXISTS %s;", [AsIs(schema)])
            curr.execute("SET SEARCH_PATH TO %s;", [AsIs(schema)])
        try:
            yield
        finally:
            with cls.cursor() as curr:
                curr.execute("SET SEARCH_PATH TO %s;", org_search_path)
                if not persist:
                    curr.execute("DROP SCHEMA IF EXISTS %s CASCADE;", [AsIs(schema)])
                    if schema.lower() == "public":
                        curr.execute("CREATE SCHEMA IF NOT EXISTS public;")

    @classmethod
    def copy_schema(
        cls, to_schema: str, tables: Optional[List[str]] = None, from_schema: str = "public", overwrite: bool = True,
    ) -> None:
        """
        Copies tables from <from_schema> to <to_schema>. <from_schema> is
        'public' by default

        If <tables> is None all tables will be copied, otherwise only the table
        names in <tables> will be copied. If <overwrite> is True, tables of the
        same name in <to_schema> will be overwritten.
        """
        strings = {"new": AsIs(to_schema), "old": AsIs(from_schema)}
        if tables is None:
            with cls.cursor() as curr:
                curr.execute(cls.GET_TABLES_STR, [from_schema])
                tables = [t[0] for t in curr.fetchall()]
        with cls.cursor() as curr:
            curr.execute("CREATE SCHEMA IF NOT EXISTS %s;", [AsIs(to_schema)])
            for table in tables:
                if overwrite:
                    curr.execute("DROP TABLE IF EXISTS %s.%s;", [AsIs(to_schema), AsIs(table)])
                strs = {**strings, "table": AsIs(table)}
                curr.execute(cls.SCHEMA_COPY_STR, strs)

    @classmethod
    def execute_files(cls, files: List[str], *args, cursor: Optional[CursorType] = None, **kwargs) -> None:
        """
        Execute each file in <files> by passing the content of each to
        cursor.execute.

        The cursor is either obtained by calling the cursor method (passing
        the <args> and <kwargs>) or the cursor object passed as the <cursor>
        argument is used if <cursor> is not None.
        """

        def _execute_files():
            for file in files:
                with open(file) as f:
                    cursor.execute(f.read())

        if cursor is None:
            with cls.cursor(*args, **kwargs) as cursor:
                _execute_files()
        else:
            _execute_files()
