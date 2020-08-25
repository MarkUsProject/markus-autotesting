"""
Custom Exception Types
"""


class AutotestError(Exception):
    """ Generic Autotester Error """


class TesterCreationError(AutotestError):
    """ Error raised when a tester environment could not be created """


class TesterUserError(AutotestError):
    """ Error raised when a tester user is not available """


class TestScriptFilesError(AutotestError):
    """ Error raised when test script files cannot be found for a given test job """


class TestParameterError(AutotestError):
    """
    Error raised when the value of the arguments used to enqueue a test job are invalid
    """
