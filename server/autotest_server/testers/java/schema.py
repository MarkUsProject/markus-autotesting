from __future__ import annotations
from typing import Annotated

from msgspec import Meta
from markus_autotesting_core.types import BaseTestData, BaseTesterSettings


class JavaTesterSettings(BaseTesterSettings):
    """The settings for the Java tester."""

    test_data: Annotated[list[JavaTestData], Meta(title="Test Groups", min_length=1)]


class JavaTestData(BaseTestData, kw_only=True):
    """The `test_data` specification for the Java tester."""

    classpath: Annotated[str, Meta(title="Java Class Path")] = "."
    sources_path: Annotated[str, Meta(title="Java Sources (glob)")] = ""
