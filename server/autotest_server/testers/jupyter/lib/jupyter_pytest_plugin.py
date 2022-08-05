import pytest


class JupyterPlugin:
    """
    Pytest plugin to collect and parse test results as well
    as any errors during the test collection process.
    """

    def __init__(self) -> None:
        """
        Initialize a pytest plugin for collecting results
        """
        self.results = {}

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_runtest_makereport(self, item, call):
        """
        Implement a pytest hook that is run when reporting the
        results of a given test item.

        Records the results of each test in the self.results
        attribute.

        See pytest documentation for a description of the parameter
        types and the return value.
        """
        outcome = yield
        rep = outcome.get_result()
        if rep.failed or item.nodeid not in self.results:
            self.results[item.nodeid] = {
                "status": "failure" if rep.failed else "success",
                "name": item.nodeid,
                "errors": str(rep.longrepr) if rep.failed else "",
                "description": item.obj.__doc__,
            }
        return rep

    def pytest_collectreport(self, report):
        """
        Implement a pytest hook that is run after the collector has
        finished collecting all tests.

        Records a test failure in the self.results attribute if the
        collection step failed.

        See pytest documentation for a description of the parameter
        types and the return value.
        """
        if report.failed:
            self.results[report.nodeid] = {
                "status": "error",
                "name": report.nodeid,
                "errors": str(report.longrepr),
                "description": None,
            }
