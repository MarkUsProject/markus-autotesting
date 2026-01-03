from __future__ import annotations
from typing import Annotated

from msgspec import Meta
from markus_autotesting_core.types import AutotestFile, BaseTestData, BaseTesterSettings


class CustomTesterSettings(BaseTesterSettings, tag="custom"):
    """The settings for the custom tester."""

    test_data: Annotated[list[CustomTestData], Meta(title="Test Groups", min_length=1)]


class CustomTestData(BaseTestData, kw_only=True):
    """The `test_data` specification for the custom tester."""

    script_files: Annotated[
        list[AutotestFile],
        Meta(title="Test files", min_length=1, extra_json_schema={"uniqueItems": True}),
    ]
    """The file(s) that contain the tests to execute."""
