import psycopg2
from psycopg2 import extras
import os
import getpass
from typing import Optional, IO, AnyStr, List, Collection

class SQLTestHelper:
    """
    Provides access to the database provided to the current tester user. 
    """
    _pg_prefix = os.environ.get('POSTGRESPREFIX', '')
    _alternate_cursors = {
        'dict': extras.RealDictCursor,
        'namedtuple': extras.NamedTupleCursor,
        'tuple': psycopg2.extensions.cursor
    }
    _default_cusor_type='namedtuple'

    def __init__(self):
        """ Initialize a new SQLTestHelper instance and connect to the user's database """
        user = getpass.getuser()
        database = f'{self._pg_prefix}{user}'
        self._connection = psycopg2.connect(database=database, user=user)

    def new_cursor(self, cursor_type: Optional[str] = None, **kwargs) -> psycopg2.extensions.cursor:
        """
        Return a new psycopg2.cursor object connected to the user's database.

        The cursor_type parameter is a convenient way to specify the return type
        of any data fetched from the database by calling the `fetchone` or `fetchall`
        methods on the cursor object before it is closed.

        The default is to return a list of namedtuples but other options are:

        'tuple': return list of tuples
        'dict': return list of dicts
        'namedtuple': return list of namedtuples (DEFAULT)        

        Additional kwargs will be passed to the initializer for the psycopg2.cursor
        object. Therefor specifying a cursor_factory kwarg will override the cursor_type. 

        Since this method returns a psycopg2.cursor object it can be called like a 
        context manager as well:

            h = SQLTestHelper()

            c = h.new_cursor()
            c.execute(my_query)
            c.commit()
            
            # is roughly equivalent to 

            with h.new_cursor() as c:
                c.execute(my_query)
        """
        if cursor_type is None:
            cursor_type = self._default_cusor_type
        cursor_factory = self._alternate_cursors.get(cursor_type, cursor_type)
        return self._connection.cursor(**{'cursor_factory': cursor_factory, **kwargs})

    def execute(self, query: str, cursor_type: Optional[str] = None) -> Optional[List[Collection]]:
        """
        Return the results of executing query if any results are returned after the query
        is executed (eg: a SELECT query will return results but an INSERT query will not)

        See the docstring for the `new_cursor` method for a description of the cursor_type
        parameter.
        """
        with self._connection:
            with self.new_cursor(cursor_type) as cursor:
                cursor.execute(query)
                if cursor.description:
                    return cursor.fetchall()
    
    def execute_file(self, open_file: IO[AnyStr], cursor_type: Optional[str] = None) -> Optional[List[Collection]]:
        """
        Return the result of executing all queries in open_file. This will read the file object
        to the end and the caller is responsible for closing the file afterwards. 

        See the docstring for the `new_cursor` method for a description of the cursor_type
        parameter.       
        """
        return self.execute(open_file.read(), cursor_type)

    def get_all_table_names(self, schema: str ='public') -> List[str]:
        """
        Return a list of all table names in the specified schema (default is 'public')
        """
        query = f"SELECT table_name FROM information_schema.tables where table_schema = '{schema}';"
        return [t[0] for t in self.execute(query, cursor_type='list')]

    def get_table_info(self, table_name: str, schema: str = 'public', cursor_type: Optional[str] = None) -> Optional[Collection]:
        """
        Return information about the table table_name found in the given schema (default is 'public').

        See the docstring for the `new_cursor` method for a description of the cursor_type
        parameter.
        """
        query = f"SELECT * FROM information_schema.tables where table_schema = '{schema}' AND table_name = '{table_name}';"
        result = self.execute(query, cursor_type=cursor_type)
        if result:
            return result[0]
