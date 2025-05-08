from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, List, Optional, Union, Literal, Type

from msgspec import Meta, Struct

FilesList = str
TestDataCategories = str
InstalledTesters = str


class BaseEnvData(Struct, kw_only=True):
    """Base class for environment data structures"""

    pass


class BaseTestSpecs(Struct, kw_only=True):
    """Base class for test data structures"""

    script_files: Annotated[List[FilesList], Meta(title="Test files")]
    timeout: Annotated[int, Meta(title="Timeout")] = 30
    category: Optional[
        Annotated[
            List[TestDataCategories], Meta(title="Category", min_length=1, extra_json_schema={"uniqueItems": True})
        ]
    ] = None
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


class REnvData(BaseEnvData, kw_only=True):
    renv_lock: Optional[Annotated[bool, Meta(title="Use renv to set up environment")]] = False
    requirements: Optional[Annotated[str, Meta(title="Package requirements")]] = None


class PyTAEnvData(PythonEnvData, kw_only=True):
    pyta_version: Optional[Annotated[str, Meta(title="PyTA version")]] = None


class HaskellTestSpecs(BaseTestSpecs, kw_only=True):
    resolver_version: Annotated[str, Meta(title="Resolver version")]
    test_timeout: Annotated[int, Meta(title="Per-test timeout")] = 10
    test_cases: Annotated[int, Meta(title="Number of test cases (QuickCheck)")] = 100


class JavaTestSpecs(BaseTestSpecs, kw_only=True):
    classpath: Optional[Annotated[str, Meta(title="Java Class Path")]] = "."
    sources_path: Optional[Annotated[str, Meta(title="Java Sources (glob)")]] = ""


class JupyterScriptFile(Struct, kw_only=True):
    test_file: Annotated[FilesList, Meta(title="Test file")]
    student_file: Annotated[str, Meta(title="Student file")]
    test_merge: Annotated[bool, Meta(title="Test that files can be merged")] = False


class JupyterTestSpecs(BaseTestSpecs, kw_only=True):
    script_files: Annotated[
        List[JupyterScriptFile], Meta(title="Test files", min_length=1, extra_json_schema={"uniqueItems": True})
    ] = []
    feedback_file_names: Optional[Annotated[List[str], Meta(title="Feedback files")]] = None


class CustomTestSpecs(BaseTestSpecs, kw_only=True):
    pass


class RTestSpecs(BaseTestSpecs, kw_only=True):
    pass


class PyTAStudentFile(Struct, kw_only=True):
    file_path: Optional[Annotated[str, Meta(title="Path")]] = None
    max_points: Optional[Annotated[int, Meta(title="Maximum mark")]] = 10


class PyTATestSpecs(BaseTestSpecs, kw_only=True):
    student_files: Annotated[List[PyTAStudentFile], Meta(title="Files to check", min_length=1)]
    config_file_name: Optional[Annotated[FilesList, Meta(title="PyTA configuration")]] = None
    feedback_file_names: Optional[Annotated[List[str], Meta(title="Feedback files")]] = None
    upload_annotations: Optional[Annotated[bool, Meta(title="Upload Annotations")]] = None


class RacketScriptFile(Struct, kw_only=True):
    script_file: Optional[Annotated[FilesList, Meta(title="Test file")]] = None
    test_suite_name: Optional[Annotated[str, Meta(title="Test suite name")]] = "all-tests"


class RacketTestSpecs(BaseTestSpecs, kw_only=True):
    script_files: Annotated[List[RacketScriptFile], Meta(title="Test files", min_length=1)]
    feedback_file_names: Optional[Annotated[List[str], Meta(title="Feedback files")]] = None


class PyTesterSchema(BaseTesterSchema, kw_only=True):
    env_data: Annotated[PythonEnvData, Meta(title="Python environment")]
    test_data: Annotated[List[PyTestSpecs], Meta(title="Test Groups")]
    _env: Optional[dict[str, str]] = None


class PyTestSpecs(BaseTestSpecs, kw_only=True):
    output_verbosity: Optional[Annotated[int | str, Meta(title="Output verbosity")]] = None
    tester: Optional[Annotated[Literal["pytest", "unittest"], Meta(title="Python tester")]] = None


class CustomTesterSchema(BaseTesterSchema, kw_only=True):
    test_data: Optional[Annotated[List[CustomTestSpecs], Meta(title="Test Groups")]] = None


class HaskellTesterSchema(BaseTesterSchema, kw_only=True):
    test_data: Optional[Annotated[List[HaskellTestSpecs], Meta(title="Test Groups")]] = None


class JavaTesterSchema(BaseTesterSchema, kw_only=True):
    test_data: Optional[Annotated[List[JavaTestSpecs], Meta(title="Test Groups")]] = None
    _env: dict[str, str]


class JupyterTesterSchema(BaseTesterSchema, kw_only=True):
    env_data: Annotated[PythonEnvData, Meta(title="Python environment")]
    test_data: Optional[Annotated[List[JupyterTestSpecs], Meta(title="Test Groups")]] = None


class PyTATesterSchema(BaseTesterSchema, kw_only=True):
    env_data: Annotated[PyTAEnvData, Meta(title="Python environment")]
    test_data: Optional[Annotated[List[PyTATestSpecs], Meta(title="Test Groups")]] = None


class RTesterSchema(BaseTesterSchema, kw_only=True):
    env_data: Annotated[REnvData, Meta(title="R environment")]
    test_data: Optional[Annotated[List[RTestSpecs], Meta(title="Test Groups")]] = None


class RacketTesterSchema(BaseTesterSchema, kw_only=True):
    test_data: Optional[Annotated[List[RacketTestSpecs], Meta(title="Test Groups")]] = None


TestSpecs = Union[
    PyTestSpecs,
    HaskellTestSpecs,
    JavaTestSpecs,
    JupyterTestSpecs,
    PyTATestSpecs,
    RacketTestSpecs,
    CustomTestSpecs,
    RTestSpecs,
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


class TesterType(Enum):
    py: Literal["py"] = "py"
    custom: Literal["custom"] = "custom"
    haskell: Literal["haskell"] = "haskell"
    java: Literal["java"] = "java"
    jupyter: Literal["jupyter"] = "jupyter"
    pyta: Literal["pyta"] = "pyta"
    r: Literal["r"] = "r"
    racket: Literal["racket"] = "racket"

    def get_schema_type(self) -> Type[TesterSchemas]:
        """Get the schema for this tester type"""
        return {
            TesterType.py: PyTesterSchema,
            TesterType.custom: CustomTesterSchema,
            TesterType.haskell: HaskellTesterSchema,
            TesterType.java: JavaTesterSchema,
            TesterType.jupyter: JupyterTesterSchema,
            TesterType.pyta: PyTATesterSchema,
            TesterType.r: RTesterSchema,
            TesterType.racket: RacketTesterSchema,
        }[self]


class TestSettingsModel(Struct, kw_only=True):
    testers: Annotated[List[TesterSchemas], Meta(title="Testers", min_length=1)]
    _user: Optional[str] = None
    _last_access: Optional[int] = None
    _files: Optional[str] = None
    _env_status: Optional[str] = None
