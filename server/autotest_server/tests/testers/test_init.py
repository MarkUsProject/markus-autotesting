import types

import pytest

import autotest_server.testers as testers


@pytest.fixture
def setup_modules(monkeypatch):
    """Replace each tester's setup module with a fake one. Return the fakes by tester name."""
    modules = {}

    def fake_module(tester):
        module = types.SimpleNamespace(__file__=f"/testers/{tester}/setup.py", installed=False)

        def install():
            if tester == "broken":
                raise RuntimeError("missing dependency")
            module.installed = True

        module.install = install
        module.settings = lambda: (
            {"title": tester.capitalize()},
            {f"{tester.capitalize()}TesterSettings": {}, f"{tester}_def": {}},
        )
        return module

    def import_module(name, package=None):
        tester = name.removeprefix(".").removesuffix(".setup")
        return modules.setdefault(tester, fake_module(tester))

    monkeypatch.setattr(testers.importlib, "import_module", import_module)
    return modules


def test_install(setup_modules):
    schemas, definitions = testers.install(["py", "java"])
    assert setup_modules["py"].installed and setup_modules["java"].installed
    assert schemas == {"py": {"title": "Py"}, "java": {"title": "Java"}}
    assert definitions == {"py_def": {}, "java_def": {}}


def test_install_failure(setup_modules):
    with pytest.raises(Exception, match="broken install failed with: missing dependency") as e:
        testers.install(["py", "broken"])
    assert "/testers/broken/requirements.system" in str(e.value)
    assert isinstance(e.value.__cause__, RuntimeError)
