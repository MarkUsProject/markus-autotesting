import msgspec

from ....testers.py.schema import PyTesterSettings


def test_output_verbosity_accepts_int_for_unittest() -> None:
    """The MarkUs form emits integer verbosity (0/1/2) for unittest groups,
    so the schema must decode an int without coercing it to a string."""
    settings = msgspec.json.decode(
        b"""
        {
          "env_data": {},
          "test_data": [
            {
              "script_files": ["test.py"],
              "category": ["instructor"],
              "tester": "unittest",
              "output_verbosity": 2
            }
          ]
        }
        """,
        type=PyTesterSettings,
    )
    verbosity = settings.test_data[0].output_verbosity
    assert verbosity == 2
    assert type(verbosity) is int


def test_output_verbosity_accepts_string_for_pytest() -> None:
    """The MarkUs form emits string traceback styles for pytest groups,
    so the schema must decode a string without coercing it to an int."""
    settings = msgspec.json.decode(
        b"""
        {
          "env_data": {},
          "test_data": [
            {
              "script_files": ["test.py"],
              "category": ["instructor"],
              "tester": "pytest",
              "output_verbosity": "short"
            }
          ]
        }
        """,
        type=PyTesterSettings,
    )
    verbosity = settings.test_data[0].output_verbosity
    assert verbosity == "short"
    assert type(verbosity) is str
