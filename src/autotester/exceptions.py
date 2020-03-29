"""
Custom Exception Type for use in MarkUs
"""


class MarkUsError(Exception):
    """ Generic MarkUs Error """


class TesterCreationError(MarkUsError):
    """ Error raised when a tester environment could not be created """


class TesterUserError(MarkUsError):
    """ Error raised when a tester user is not available """


class JobArgumentError(MarkUsError):
    """ Error raised when a test job is enqueued with the wrong arguments """


class InvalidQueueError(MarkUsError):
    """ Error raised when a queue cannot be found to enqueue a test job """


class TestScriptFilesError(MarkUsError):
    """ Error raised when test script files cannot be found for a given test job """


class TestParameterError(MarkUsError):
    """
    Error raised when the value of the arguments used to enqueue a test job are invalid
    """
