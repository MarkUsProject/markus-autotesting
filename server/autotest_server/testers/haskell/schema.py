from __future__ import annotations
from typing import Annotated

from msgspec import Meta, Struct
from markus_autotesting_core.types import BaseTestData, BaseTesterSettings

from .config import STACK_RESOLVER


class HaskellTesterSettings(BaseTesterSettings):
    """The settings for the Haskell tester."""

    env_data: Annotated[HaskellEnvData, Meta(title="Haskell environment")]
    test_data: Annotated[list[HaskellTestData], Meta(title="Test Groups", min_length=1)]


class HaskellTestData(BaseTestData, kw_only=True):
    """The `test_data` specification for the Haskell tester."""

    test_timeout: Annotated[int, Meta(title="Per-test timeout")] = 10
    test_cases: Annotated[int, Meta(title="Number of test cases (QuickCheck)")] = 100


class HaskellEnvData(Struct, kw_only=True):
    """Settings for the Haskell environment"""

    resolver_version: Annotated[str, Meta(title="Stackage LTS resolver version")] = STACK_RESOLVER
