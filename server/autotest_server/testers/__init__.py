import os

_TESTERS = ("custom", "haskell", "java", "py", "pyta", "racket")


def install(testers=_TESTERS):
    import importlib

    settings = {}
    for tester in testers:
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
        settings[tester] = mod.settings()
    return settings
