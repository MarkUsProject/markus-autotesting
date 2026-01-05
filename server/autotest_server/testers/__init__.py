from __future__ import annotations

import importlib
import os

_TESTERS = ("ai", "custom", "haskell", "java", "jupyter", "py", "pyta", "r", "racket")


def install(testers: list[str] = _TESTERS) -> tuple[dict, dict]:
    installed_testers = []
    for tester in testers:
        mod = importlib.import_module(f".{tester}.setup", package="autotest_server.testers")
        try:
            print(f"[AUTOTESTER] calling autotest_server.testers.{tester}.setup.install()")
            mod.install()
        except Exception as e:
            msg = (
                f"{tester} install failed with: {e}\n"
                "You may try to install the tester manually by running the following script:\n\t"
                f"{os.path.join(os.path.dirname(os.path.realpath(mod.__file__)), 'requirements.system')}"
                " and then rerunning this function."
            )
            raise Exception(msg) from e
        installed_testers.append(tester)
    return get_settings(installed_testers)


def get_settings(testers: list[str] = _TESTERS) -> tuple[dict, dict]:
    """Return JSON schemas for the settings for the given testers.

    The return values are:
    1. A dictionary mapping tester name to JSON schema
    2. A dictionary of JSON schema definitions used by the tester schemas
    """
    schemas = {}
    definitions = {}
    for tester in testers:
        mod = importlib.import_module(f".{tester}.setup", package="autotest_server.testers")
        tester_schema, tester_definitions = mod.settings()
        if "title" in tester_schema and f"{tester_schema['title']}TesterSettings" in tester_definitions:
            tester_definitions.pop(f"{tester_schema['title']}TesterSettings")
        schemas[tester] = tester_schema
        definitions.update(tester_definitions)

    return schemas, definitions
