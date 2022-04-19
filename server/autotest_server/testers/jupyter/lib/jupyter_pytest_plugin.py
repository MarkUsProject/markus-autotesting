import pytest
from notebook_helper import importer
import re
import traceback


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

    def pytest_collect_file(self, parent, path):
        if path.ext == ".ipynb":
            return IpynbFile.from_parent(parent, fspath=path)


class IpynbFile(pytest.File):
    TEST_PATTERN = re.compile(r"(?i)^\s*#+\s*(test.*?)\s*$")

    def collect(self):
        mod = importer.import_from_path(self.fspath)
        setup_cells = []
        for cell in importer.get_cells(mod):
            lines = cell.source.splitlines() or [""]  # dummy list so the next line works
            match = re.match(self.TEST_PATTERN, lines[0])
            if match and match.group(1):
                yield IpynbItem.from_parent(self, name=match.group(1), test_cell=cell, setup_cells=setup_cells, mod=mod)
                setup_cells = []
            else:
                setup_cells.append(cell)


class IpynbItem(pytest.Item):
    def __init__(self, name, parent, test_cell, setup_cells, mod):
        super().__init__(name, parent)
        self.test_cell = test_cell
        self.setup_cells = setup_cells
        self.mod = mod
        self._last_cell = None

    def runtest(self) -> None:
        for cell in self.setup_cells:
            self._last_cell = cell
            cell.run()
        self._last_cell = self.test_cell
        self.test_cell.run()

    @property
    def obj(self):
        return self.test_cell

    def repr_failure(self, excinfo, style=None):
        try:
            for tb in reversed(excinfo.traceback):
                if excinfo.typename == "SyntaxError" or str(tb.frame.code.path).startswith(self.mod.__file__):
                    err_line = tb.lineno
                    cell_lines = [
                        f"-> {l}" if i == err_line else f"   {l}"
                        for i, l in enumerate("".join(self._last_cell.source).splitlines())
                    ]
                    lines = "\n".join(cell_lines)
                    return f"{lines}\n\n{excinfo.exconly()}"
        except Exception:
            return f"Error when reporting test failure for {self.name}:\n{traceback.format_exc()}"

    def reportinfo(self):
        return self.fspath, 0, self.name
