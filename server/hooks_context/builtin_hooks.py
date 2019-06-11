"""
Builtin hooks used by hooks_context.Hooks
"""

import os
import sys
import json
import glob
from pathlib import Path
from hooks_context.utils import add_path

HOOKS = {'upload_feedback_file'    : {'context': 'after_each'},
         'upload_feedback_to_repo' : {'requires': ['clear_feedback_file'], 
                                      'context': 'after_each'},
         'upload_annotations'      : {'context': 'after_each'},
         'clear_feedback_file'     : {'context': 'before_each'}}

def clear_feedback_file(feedback_file, test_data, **kwargs):
    """
    Remove any previous feedback file before the tests run.
    """
    feedback_file = test_data.get('feedback_file_name', '')
    pass

def upload_feedback_to_repo(api, assignment_id, group_id, group_repo_name, test_data, **kwargs):
    """
    Upload the feedback file to the repo group_repo_name.
    """
    feedback_file = test_data.get('feedback_file_name', '')
    pass

def upload_feedback_file(api, assignment_id, group_id, test_data, **kwargs):
    """
    Upload the feedback file using MarkUs' api.
    """
    feedback_file = test_data.get('feedback_file_name', '')
    if os.path.isfile(feedback_file):
        with open(feedback_file) as feedback_open:
            api.upload_feedback_file(assignment_id, group_id, feedback_file, feedback_open.read())
            
def upload_annotations(api, assignment_id, group_id, test_data, **kwargs):
    """
    Upload annotations using MarkUs' api.
    """
    feedback_file = test_data.get('feedback_file_name', '')
    annotations_name = os.path.splitext(feedback_file)[0]+'.json'
    if os.path.isfile(annotations_name):
        with open(annotations_name) as annotations_open:
            api.upload_annotations(assignment_id, group_id, json.load(annotations_open))

## DEFAULT TESTER HOOKS ##

def _load_default_hooks():
    """
    Return a dictionary containing all hooks loaded from any default_hooks.py
    files in any of the bin/ directories for each tester.
    """
    glob_pat = os.path.join(Path(__file__).resolve().parents[2], 'testers', 'testers', '*', 'bin', 'default_hooks.py')
    defaults = {}
    for hooks_file in glob.glob(glob_pat):
        bin_dir = os.path.dirname(hooks_file)
        with add_path(bin_dir):
            default_hooks = __import__('default_hooks')
            for hook in default_hooks.HOOKS:
                defaults[hook.__name__] = hook
    return defaults

DEFAULT_HOOKS = _load_default_hooks()
