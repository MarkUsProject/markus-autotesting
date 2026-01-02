from __future__ import annotations
from enum import Enum
import shutil
from typing import Annotated, Optional

from msgspec import Meta, Struct
from markus_autotesting_core.types import AutotestFile, BaseTestData, BaseTesterSettings


PYTHON_VERSIONS = [f"3.{x}" for x in range(11, 14) if shutil.which(f"python3.{x}")]
PythonVersion = Enum("PythonVersion", {v.replace(".", "_"): v for v in PYTHON_VERSIONS})


class JupyterTesterSettings(BaseTesterSettings):
    """The settings for the Jupyter tester."""

    env_data: Annotated[JupyterEnvData, Meta(title="Python environment")]
    test_data: Annotated[list[JupyterTestData], Meta(title="Test Groups", min_length=1)]


class JupyterTestData(BaseTestData, kw_only=True):
    """The `test_data` specification for the Jupyter tester."""

    script_files: Annotated[list[JupyterScriptFile], Meta(title="Test files", min_length=1)]
    """The file(s) that contain the tests to execute."""


class JupyterScriptFile(Struct, kw_only=True):
    """The configuration for a single Jupyter test file."""

    test_file: Annotated[AutotestFile, Meta(title="Test file")]
    student_file: Annotated[str, Meta(title="Student file")]
    test_merge: Annotated[bool, Meta(title="Test that files can be merged")] = False


class JupyterEnvData(Struct, kw_only=True):
    """The settings for the Python environment."""

    python_version: Annotated[PythonVersion, Meta(title="Python version")] = PYTHON_VERSIONS[-1]
    pip_requirements: Optional[Annotated[str, Meta(title="Package requirements")]] = None
    pip_requirements_file: Optional[Annotated[str, Meta(title="Package requirements file")]] = None
