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
        cls.create_connection()
        with cls.schema('solution_schema'):
            
            cls.execute_files(['schema.ddl', cls.data_file])
            
            with cls.cursor() as curr:
                curr.execute(cls.query)
                cls.solution_data = curr.fetchall()
            
            with cls.schema('test_schema'):
                cls.copy_schema('test_schema', from_schema='solution_schema')
                cls.execute_files(['submission.sql'])
                with cls.cursor() as curr:
                    curr.execute("SELECT * FROM correct_no_order;")
                    cls.student_data = curr.fetchall()              

    @classmethod
    def teardown_class(cls):
        cls.close_connection()

    def test_unordered_data(self):
        assert set(self.solution_data) == set(self.student_data)

    def test_ordered_data(self):
        assert self.solution_data == self.student_data

    def test_single_column_unordered(self):
        assert {s[0] for s in self.solution_data} == {s[0] for s in self.student_data}

    def test_falsy_same_as_null(self):
        nulled_sol_data = {tuple(x or None for x in s) for s in self.solution_data}
        nulled_stu_data = {tuple(x or None for x in s) for s in self.student_data}
        assert nulled_sol_data == nulled_stu_data

    def test_schema_gone(self):
        with self.cursor() as curr:
            curr.execute(self.GET_TABLES_STR, ['test_schema'])
            assert len(curr.fetchall()) == 0


class TestDataset2(TestDataset1):
    data_file = 'data2.sql'
