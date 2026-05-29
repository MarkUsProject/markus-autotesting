from __future__ import annotations
from typing import Annotated

from msgspec import Meta, Struct
from markus_autotesting_core.types import AutotestFile, BaseTestData, BaseTesterSettings


class RacketTesterSettings(BaseTesterSettings):
    """The settings for the Racket tester."""

    test_data: Annotated[list[RacketTestData], Meta(title="Test Groups", min_length=1)]


class RacketTestData(BaseTestData, kw_only=True):
    """The `test_data` specification for the Racket tester."""

    script_files: Annotated[list[_RacketScriptFile], Meta(title="Test files", min_length=1)]
    """The file(s) that contain the tests to execute."""


class _RacketScriptFile(Struct, kw_only=True):
    """The configuration for a single Racket test file."""

    script_file: Annotated[AutotestFile, Meta(title="Test file")]
    test_suite_name: Annotated[str, Meta(title="Test suite name")] = "all-tests"
