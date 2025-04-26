import os

from .models import TesterType


def install(testers_to_install: list[TesterType]) -> tuple[list[TesterType], dict[TesterType, dict]]:
    """Tries to install testers. Returns successfully installed testers and their settings."""
    import importlib

    installed_testers = []
    installed_tester_settings = {}
    for tester_enum in testers_to_install:
        tester = tester_enum.value
        mod = importlib.import_module(f".{tester}.setup", package="autotest_server.testers")
        try:
            mod.install()
        except Exception as e:
            msg = (
                f"{tester} install failed with: {e}\n"
                "You may try to install the tester manually by running the following script:\n\t"
                f"{os.path.join(os.path.dirname(os.path.realpath(mod.__file__)), 'requirements.system')}"
                " and then rerunning this function."
            )
            raise Exception(msg) from e
        installed_testers.append(tester_enum)
        installed_tester_settings[tester_enum] = mod.settings()
    return installed_testers, installed_tester_settings
