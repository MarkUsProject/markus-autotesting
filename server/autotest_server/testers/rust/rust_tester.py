import os
import subprocess
from typing import Type, Optional
import json
from ..tester import Tester, Test, TestError
from ..specs import TestSpecs
from pathlib import Path
import re

TEST_IDENTIFIER_REGEX = re.compile("^((?P<exec>.*)\\$)?(?P<test>.*)$")


def parse_test_identifier(identifier: str) -> tuple[str, str]:
    result = TEST_IDENTIFIER_REGEX.match(identifier)

    return result.group("exec"), result.group("test")


class RustTest(Test):
    def __init__(self, tester: "RustTester", executable: str, test: str, success: bool, message: str) -> None:
        self.executable = executable
        self.test = test
        self.success = success
        self.message = message

        super().__init__(tester)

    @property
    def test_name(self) -> str:
        return self.test

    def run(self) -> str:
        if self.success:
            return self.passed(message=self.message)
        else:
            return self.failed(message=self.message)


def parse_adjacent_json(text: str) -> list[dict]:
    skip = {"\n", "\r"}

    i = 0
    decoder = json.JSONDecoder()

    items = []

    while i < len(text):
        value, i = decoder.raw_decode(text, i)

        items.append(value)

        while i < len(text) and text[i] in skip:
            i += 1

    return items


class RustTester(Tester):
    def __init__(self, specs: TestSpecs, test_class: Type[RustTest] = RustTest) -> None:
        super().__init__(specs, test_class)

    def parse_test_events(self, items: list[dict]) -> list[RustTest]:
        tests = []

        for item in items:
            # Ignore suite events.
            if item["type"] != "test":
                continue

            event = item["event"]

            finished_events = {"failed", "ok"}

            if event not in finished_events:
                continue

            executable, test = parse_test_identifier(item["name"])

            output = item["stdout"] if event == "failed" else ""

            tests.append(self.test_class(self, executable, test, event == "ok", output))

        return tests

    # This should likely be moved to setup.py's create_environment.
    def rust_env(self) -> dict:
        # Hint to /bin/sh that it should look in $HOME/.cargo/bin.
        # Despite .profile pointing to this directory, /bin/dash does not want to acknowledge it.
        # There is conflicting information online as to whether-or-not .profile is respected by dash.
        rust_home_path = os.path.join(Path.home(), ".cargo", "bin")

        env = os.environ.copy()

        env["PATH"] = rust_home_path + ":" + env["PATH"]

        return env

    def compile_rust_tests(self, directory: str) -> subprocess.CompletedProcess:
        command = ["cargo", "nextest", "run", "--no-run", "--color", "never"]

        env = self.rust_env()

        return subprocess.run(command, cwd=directory, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # We need a way to get machine-readable output from cargo test (why are we using nextest?).
    # Here are the options I've explored:
    #  - cargo-test by default outputs human-readable strings.
    #    These strings might change in format over time, and I figure one tests stdout could bleed into another.
    #  - cargo-test supports machine-readable strings (via `cargo test -- --format json`).
    #    This option is nightly rust only, and enforcing nightly rust could cause other issues.
    #  - cargo-nextest supports experimental machine-readable output.
    #    While machine-readable output is experimental, it's based on yhr libtest standard that cargo test would use.
    #    nextest should also interact very similarly to `cargo test`. It should be very simple to swap to cargo-test.
    #    It's also reliable and only requires Rust 1.36 or earlier for running.
    def run_rust_tests(self, directory: str, module: Optional[str]) -> subprocess.CompletedProcess:
        command = ["cargo", "nextest", "run", "--no-fail-fast", "--message-format", "libtest-json", "--color", "never"]

        # Prevent CLI options from being propagated.
        if module is not None and '-' in module:
            command.append(module)

        # Machine-readable output is experimental with Nextest.
        env = self.rust_env()
        env["NEXTEST_EXPERIMENTAL_LIBTEST_JSON"] = "1"

        return subprocess.run(command, cwd=directory, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def run_and_parse_rust_tests(self, directory: str, module: Optional[str]) -> list[RustTest]:
        test_results = self.run_rust_tests(directory, module)

        json_string = test_results.stdout.decode("utf-8")
        test_events = parse_adjacent_json(json_string)

        return self.parse_test_events(test_events)

    @Tester.run_decorator
    def run(self) -> None:
        # Awkwardly, cargo doesn't have a great way of running files.
        # Instead, it can run all the tests in a module (which is named after a file barring .rs and the path).

        try:
            compile_result = self.compile_rust_tests(".")

            if compile_result.returncode != 0:
                raise TestError(compile_result.stderr.decode("utf-8"))
        except subprocess.CalledProcessError as e:
            raise TestError(e)

        module = self.specs.get("test_data", "test_module")

        if module is not None:
            module = module.strip()

        if module == "":
            module = None

        tests = self.run_and_parse_rust_tests(".", module)

        for test in tests:
            print(test.run(), flush=True)
