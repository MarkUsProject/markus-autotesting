from __future__ import annotations
from typing import Annotated

from msgspec import field, Meta, Struct
from markus_autotesting_core.types import BaseTestData, BaseTesterSettings


class RTesterSettings(BaseTesterSettings):
    """The settings for the R tester."""

    env_data: Annotated[REnvData, Meta(title="R environment")]
    test_data: Annotated[list[RTestData], Meta(title="Test Groups", min_length=1)]


class REnvData(Struct, kw_only=True):
    """Settings for the R environment"""

    renv_lock: Annotated[bool, Meta(title="Use renv to set up environment")] = field(default=False, name="renv.lock")
    requirements: Annotated[str, Meta(title="R package requirements")] = ""


class RTestData(BaseTestData, kw_only=True):
    """The `test_data` specification for the R tester."""

    pass
