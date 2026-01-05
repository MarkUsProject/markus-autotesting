from __future__ import annotations
from enum import Enum
import shutil
from typing import Annotated, Literal

from msgspec import Meta, Struct
from markus_autotesting_core.types import BaseTestData, BaseTesterSettings


PYTHON_VERSIONS = [f"3.{x}" for x in range(11, 14) if shutil.which(f"python3.{x}")]
PythonVersion = Enum("PythonVersion", {v.replace(".", "_"): v for v in PYTHON_VERSIONS})


class PyTesterSettings(BaseTesterSettings):
    """The settings for the Python tester."""

    env_data: Annotated[PythonEnvData, Meta(title="Python environment")]
    test_data: Annotated[list[PyTestData], Meta(title="Test Groups", min_length=1)]


class PythonEnvData(Struct, kw_only=True):
    """The settings for the Python environment."""

    python_version: Annotated[PythonVersion, Meta(title="Python version")] = PYTHON_VERSIONS[-1]
    pip_requirements: Annotated[str, Meta(title="Package requirements")] = ""
    pip_requirements_file: Annotated[str, Meta(title="Package requirements file")] = ""


class PyTestData(BaseTestData, kw_only=True):
    """The `test_data` specification for the Python tester."""

    tester: Annotated[Literal["unittest", "pytest"], Meta(title="Test runner")] = "pytest"
    output_verbosity: Annotated[
        Literal["", "0", "1", "2", "short", "auto", "long", "no", "line", "native"], Meta(title="Output verbosity")
    ] = ""
