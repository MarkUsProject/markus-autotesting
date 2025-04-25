from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, List, Optional, Union, Literal

from msgspec import Meta, Struct, field

FilesList = str
TestDataCategories = str
InstalledTesters = str


class BaseEnvData(Struct, kw_only=True):
    """Base class for environment data structures"""

    pass


class BaseTestDatum(Struct, kw_only=True):
    """Base class for test data structures"""

    script_files: Annotated[List[FilesList], Meta(title="Test files")]
    timeout: Annotated[int, Meta(title="Timeout")]
    category: Optional[Annotated[List[TestDataCategories], Meta(title="Category")]] = None
    feedback_file_names: Annotated[List[str], Meta(title="Feedback files")] = []
    extra_info: dict[str, Any] = {}
    points: dict[str, int] = {}


class BaseTesterSchema(
    Struct,
    tag=lambda x: x.removesuffix("TesterSchema").lower(),
    tag_field="tester_type",
    frozen=True,
    forbid_unknown_fields=True,
    kw_only=True,
):
    """Base class for tester schemas"""

    test_data: Optional[Any] = None

    @property
    def tester_type(self) -> str:
        return self.__class__.__name__.removesuffix("TesterSchema").lower()


class PythonEnvData(BaseEnvData, kw_only=True):
    python_version: Annotated[str, Meta(title="Python version")]
    pip_requirements: Optional[Annotated[str, Meta(title="Package requirements")]] = None
    pip_requirements_file: Optional[Annotated[str, Meta(title="Package requirements file")]] = None


class HaskellEnvData(BaseEnvData, kw_only=True):
    resolver_version: Annotated[str, Meta(title="Resolver version")]


class REnvData(BaseEnvData, kw_only=True):
    renv_lock: Optional[Annotated[bool, Meta(title="Use renv to set up environment")]] = field(
        name="renv.lock", default=False
    )
    requirements: Optional[Annotated[str, Meta(title="Package requirements")]] = None


class PyTAEnvData(PythonEnvData, kw_only=True):
    pyta_version: Optional[Annotated[str, Meta(title="PyTA version")]] = None


class TesterType(Enum):
    py = "py"
    custom = "custom"
    haskell = "haskell"
    java = "java"
    jupyter = "jupyter"
    pyta = "pyta"
    r = "r"
    racket = "racket"


class HaskellTestDatum(BaseTestDatum, kw_only=True):
    test_timeout: Annotated[int, Meta(title="Per-test timeout")]
    test_cases: Annotated[int, Meta(title="Number of test cases (QuickCheck)")]


class JavaTestDatum(BaseTestDatum, kw_only=True):
    classpath: Optional[Annotated[str, Meta(title="Java Class Path")]] = None
    sources_path: Optional[Annotated[str, Meta(title="Java Sources (glob)")]] = None


class JupyterScriptFile(Struct, kw_only=True):
    test_file: Annotated[FilesList, Meta(title="Test file")]
    student_file: Annotated[str, Meta(title="Student file")]
    test_merge: Annotated[bool, Meta(title="Test that files can be merged")]


class JupyterTestDatum(BaseTestDatum, kw_only=True):
    script_files: Annotated[List[JupyterScriptFile], Meta(title="Test files")]
    timeout: Annotated[int, Meta(title="Timeout")]
    category: Optional[Annotated[List[TestDataCategories], Meta(title="Category")]] = None
    feedback_file_names: Optional[Annotated[List[str], Meta(title="Feedback files")]] = None


class PyTAStudentFile(Struct, kw_only=True):
    file_path: Optional[Annotated[str, Meta(title="Path")]] = None
    max_points: Optional[Annotated[int, Meta(title="Maximum mark")]] = 10


class PyTATestDatum(BaseTestDatum, kw_only=True):
    student_files: Annotated[List[PyTAStudentFile], Meta(title="Files to check")]
    timeout: Annotated[int, Meta(title="Timeout")]
    config_file_name: Optional[Annotated[FilesList, Meta(title="PyTA configuration")]] = None
    category: Optional[Annotated[List[TestDataCategories], Meta(title="Category")]] = None
    feedback_file_names: Optional[Annotated[List[str], Meta(title="Feedback files")]] = None
    upload_annotations: Optional[Annotated[bool, Meta(title="Upload Annotations")]] = None


class RacketScriptFile(Struct, kw_only=True):
    script_file: Optional[Annotated[FilesList, Meta(title="Test file")]] = None
    test_suite_name: Optional[Annotated[str, Meta(title="Test suite name")]] = "all-tests"


class RacketTestDatum(BaseTestDatum, kw_only=True):
    script_files: Annotated[List[RacketScriptFile], Meta(title="Test files")]
    timeout: Annotated[int, Meta(title="Timeout")]
    category: Optional[Annotated[List[TestDataCategories], Meta(title="Category")]] = None
    feedback_file_names: Optional[Annotated[List[str], Meta(title="Feedback files")]] = None


class PyTesterSchema(BaseTesterSchema, kw_only=True):
    env_data: Annotated[PythonEnvData, Meta(title="Python environment")]
    test_data: Annotated[List[PyTestDatum], Meta(title="Test Groups")]
    _env: Optional[dict[str, str]] = None


class PyTestDatum(BaseTestDatum, kw_only=True):
    output_verbosity: Optional[Annotated[int | str, Meta(title="Output verbosity")]] = None
    tester: Optional[Annotated[Literal["pytest", "unittest"], Meta(title="Python tester")]] = None


class CustomTesterSchema(BaseTesterSchema, kw_only=True):
    test_data: Optional[Annotated[List[BaseTestDatum], Meta(title="Test Groups")]] = None


class HaskellTesterSchema(BaseTesterSchema, kw_only=True):
    env_data: Annotated[HaskellEnvData, Meta(title="Haskell environment")]
    test_data: Optional[Annotated[List[HaskellTestDatum], Meta(title="Test Groups")]] = None


class JavaTesterSchema(BaseTesterSchema, kw_only=True):
    test_data: Optional[Annotated[List[JavaTestDatum], Meta(title="Test Groups")]] = None
    _env: dict[str, str]


class JupyterTesterSchema(BaseTesterSchema, kw_only=True):
    env_data: Annotated[PythonEnvData, Meta(title="Python environment")]
    test_data: Optional[Annotated[List[JupyterTestDatum], Meta(title="Test Groups")]] = None


class PyTATesterSchema(BaseTesterSchema, kw_only=True):
    env_data: Annotated[PyTAEnvData, Meta(title="Python environment")]
    test_data: Optional[Annotated[List[PyTATestDatum], Meta(title="Test Groups")]] = None


class RTesterSchema(BaseTesterSchema, kw_only=True):
    env_data: Annotated[REnvData, Meta(title="R environment")]
    test_data: Optional[Annotated[List[BaseTestDatum], Meta(title="Test Groups")]] = None


class RacketTesterSchema(BaseTesterSchema, kw_only=True):
    test_data: Optional[Annotated[List[RacketTestDatum], Meta(title="Test Groups")]] = None


TestDatum = Union[
    PyTestDatum,
    HaskellTestDatum,
    JavaTestDatum,
    JupyterTestDatum,
    PyTATestDatum,
    RacketTestDatum,
]

TesterSchemas = Union[
    PyTesterSchema,
    CustomTesterSchema,
    HaskellTesterSchema,
    JavaTesterSchema,
    JupyterTesterSchema,
    PyTATesterSchema,
    RTesterSchema,
    RacketTesterSchema,
]


class TestSettingsModel(Struct, kw_only=True):
    testers: Annotated[List[TesterSchemas], Meta(title="Testers")]
    _user: Optional[str] = None
    _last_access: Optional[int] = None
    _files: Optional[str] = None
    _env_status: Optional[str] = None
