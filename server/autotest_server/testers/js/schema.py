from __future__ import annotations
from typing import Annotated
from msgspec import Meta
from markus_autotesting_core.types import BaseTestData, BaseTesterSettings


class JsTesterSettings(BaseTesterSettings):
    """The settings for the JavaScript tester."""
    test_data: Annotated[list[JsTestData], Meta(title="Test Groups", min_length=1)]


class JsTestData(BaseTestData, kw_only=True):
    """The `test_data` specification for the JavaScript tester."""
    pass
