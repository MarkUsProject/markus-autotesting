""" 
Custom Exception Type for use in MarkUs
"""

class MarkUsError(Exception):
    pass

class TesterCreationError(MarkUsError):
    pass

class TesterUserError(MarkUsError):
    pass

class JobArgumentError(MarkUsError):
    pass


class InvalidQueueError(MarkUsError):
    pass


class TestScriptFilesError(MarkUsError):
    pass


class TestParameterError(MarkUsError):
    pass