import sql_helper as sh


class TestDataset1(sh.PSQLTest):

    data_file = 'data1.sql'
    query = """
            SELECT table1.word, table2.number
            FROM table1 JOIN table2
            ON table1.id = table2.foreign_id;
            """

    @classmethod
    def setup_class(cls):
        # create a connection to the database and store it as a class attribute.
        # this means you only have to create a connection once for the whole test class
        cls.create_connection()
        # create a new schema named 'solution_schema' and switch the search path to that schema.
        with cls.schema('solution_schema'):
            # execute your files in this schema, they will populate the schema with some tables
            cls.execute_files(['schema.ddl', cls.data_file])
            # execute the solution query in this schema, get the results and store them in a class variable
            with cls.cursor() as curr:
                curr.execute(cls.query)
                cls.solution_data = curr.fetchall()
            # create a new schema named 'test_schema' and switch the search path to that schema.
            with cls.schema('test_schema'):
                # copy all the tables in solution_schema to test_schema
                cls.copy_schema('test_schema', from_schema='solution_schema')
                # execute the student's file, this will create a table called correct_no_order
                cls.execute_files(['submission.sql'])
                # get the contents of the correct_no_order table and store it in a class variable
                with cls.cursor() as curr:
                    curr.execute("SELECT * FROM correct_no_order;")
                    cls.student_data = curr.fetchall()

    @classmethod
    def teardown_class(cls):
        # close the connection to the database when all the tests have run (not necessary but cleaner).
        cls.close_connection()

    def test_unordered_data(self):
        """ Test that the rows in the solution match the rows in the student's table (unordered) """
        assert set(self.solution_data) == set(self.student_data)

    def test_ordered_data(self):
        """ Test that the rows in the solution match the rows in the student's table (order matters) """
        assert self.solution_data == self.student_data

    def test_single_column_unordered(self):
        """ Test that the first column in the solution matches the first column in the student's table (unordered) """
        assert {s[0] for s in self.solution_data} == {s[0] for s in self.student_data}

    def test_falsy_same_as_null(self):
        """
        Test that the rows in the solution match the rows in the student's table (unordered) but treat all falsy values
        the same. Falsy values are the empty string, zero, null, etc.
        """
        nulled_sol_data = {tuple(x or None for x in s) for s in self.solution_data}
        nulled_stu_data = {tuple(x or None for x in s) for s in self.student_data}
        assert nulled_sol_data == nulled_stu_data

    def test_schema_gone(self):
        """ Test that demonstrates that the test_schema schema created in the setup_class method has been deleted """
        with self.cursor() as curr:
            curr.execute(self.GET_TABLES_STR, ['test_schema'])
            assert len(curr.fetchall()) == 0


class TestDataset2(TestDataset1):
    data_file = 'data2.sql'
