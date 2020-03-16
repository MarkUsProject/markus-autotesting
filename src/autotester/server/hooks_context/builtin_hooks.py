"""
Builtin hooks used by hooks_context.Hooks
"""

import os
import json
import pkgutil
import importlib
from typing import Dict, Any, Callable
from markusapi import Markus as MarkusApi
from autotester import testers

HOOKS = {
    "upload_feedback_file": {"context": "after_each"},
    "upload_feedback_to_repo": {
        "requires": ["clear_feedback_file"],
        "context": "after_each",
    },
    "upload_annotations": {"context": "after_each"},
    "clear_feedback_file": {"context": "before_each"},
}


def clear_feedback_file(test_data: Dict, **_kwargs: Any) -> None:
    """
    Remove any previous feedback file before the tests run.
    """
    feedback_file = test_data.get("feedback_file_name", "")
    if os.path.isfile(feedback_file):
        os.remove(feedback_file)


def upload_feedback_to_repo(
    api: MarkusApi, assignment_id: int, group_id: int, test_data: Dict, **_kwargs: Any
) -> None:
    """
    Upload the feedback file to the group's repo.
    """
    feedback_file = test_data.get("feedback_file_name", "")
    if os.path.isfile(feedback_file):
        with open(feedback_file) as feedback_open:
            api.upload_file_to_repo(
                assignment_id, group_id, feedback_file, feedback_open.read()
            )


def upload_feedback_file(
    api: MarkusApi, assignment_id: int, group_id: int, test_data: Dict, **_kwargs: Any
) -> None:
    """
    Upload the feedback file using MarkUs' api.
    """
    feedback_file = test_data.get("feedback_file_name", "")
    if os.path.isfile(feedback_file):
        with open(feedback_file) as feedback_open:
            api.upload_feedback_file(
                assignment_id, group_id, feedback_file, feedback_open.read()
            )


def upload_annotations(
    api: MarkusApi, assignment_id: int, group_id: int, test_data: Dict, **_kwargs: Any
) -> None:
    """
    Upload annotations using MarkUs' api.
    """
    annotations_name = test_data.get("annotation_file", "")
    if os.path.isfile(annotations_name):
        with open(annotations_name) as annotations_open:
            api.upload_annotations(assignment_id, group_id, json.load(annotations_open))


def _load_default_hooks() -> Dict[str, Callable]:
    """
    Return a dictionary containing all hooks loaded from any default_hooks.py in the testers package.
    """
    defaults = {}
    for _finder, name, _ispkg in pkgutil.walk_packages(
        testers.__path__, f"{testers.__name__}."
    ):
        if name.endswith("default_hooks"):
            default_hooks = importlib.import_module(name)
            for hook in default_hooks.HOOKS:
                defaults[hook.__name__] = hook
    return defaults


DEFAULT_HOOKS = _load_default_hooks()
