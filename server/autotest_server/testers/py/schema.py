from __future__ import annotations
from enum import Enum
import shutil
from typing import Annotated, Literal, Union

from msgspec import Meta, Struct
from markus_autotesting_core.types import BaseTestData, BaseTesterSettings


PYTHON_VERSIONS = [f"3.{x}" for x in range(11, 14) if shutil.which(f"python3.{x}")]
PythonVersion = Enum("PythonVersion", {v.replace(".", "_"): v for v in PYTHON_VERSIONS})


class PyTesterSettings(BaseTesterSettings):
    """The settings for the Python tester."""

    env_data: Annotated[PythonEnvData, Meta(title="Python environment")]
    test_data: Annotated[list[Union[UnittestPyTestData, PytestPyTestData]], Meta(title="Test Groups", min_length=1)]


class PythonEnvData(Struct, kw_only=True):
    """The settings for the Python environment."""

    python_version: Annotated[PythonVersion, Meta(title="Python version")] = PYTHON_VERSIONS[-1]
    pip_requirements: Annotated[str, Meta(title="Package requirements")] = ""
    pip_requirements_file: Annotated[str, Meta(title="Package requirements file")] = ""


class BasePyTestData(
    BaseTestData, kw_only=True, tag=lambda x: x.removesuffix("PyTestData").lower(), tag_field="tester"
):
    """Base class for Python test data."""

    pass


class UnittestPyTestData(BasePyTestData, kw_only=True):
    """Unittest-based Python test data."""

    output_verbosity: Annotated[Literal[0, 1, 2], Meta(title="Unittest output verbosity")] = 2


class PytestPyTestData(BasePyTestData, kw_only=True):
    """Pytest-based Python test data."""

    output_verbosity: Annotated[
        Literal["short", "auto", "long", "no", "line", "native"], Meta(title="Pytest output verbosity")
    ] = "short"
