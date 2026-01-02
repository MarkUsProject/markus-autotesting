from __future__ import annotations
from typing import Annotated

from msgspec import Meta
from markus_autotesting_core.types import BaseTestData, BaseTesterSettings


class RTesterSettings(BaseTesterSettings):
    """The settings for the R tester."""

    test_data: Annotated[list[RTestData], Meta(title="Test Groups", min_length=1)]


class RTestData(BaseTestData, kw_only=True):
    """The `test_data` specification for the R tester."""

    pass
