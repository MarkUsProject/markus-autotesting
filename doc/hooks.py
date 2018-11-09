import glob
import os
import json


def before_all(api, tests_path, assignment_id, group_id, group_repo_name):
    # clean up unwanted files
    pattern = os.path.join(tests_path, '**', '*.o')
    for file_path in glob.glob(pattern, recursive=True):
        os.remove(file_path)


def before_each(api, tests_path, assignment_id, group_id, group_repo_name):
    pass


def after_each(api, tests_path, assignment_id, group_id, group_repo_name):
    pass


def after_all(api, tests_path, assignment_id, group_id, group_repo_name):
    # upload feedback file
    feedback_name = 'feedback_pyta.txt'
    feedback_path = os.path.join(tests_path, feedback_name)
    if os.path.isfile(feedback_path):
        with open(feedback_path) as feedback_open:
            api.upload_feedback_file(assignment_id, group_id, feedback_name, feedback_open.read())
    # upload annotations
    annotations_name = 'feedback_pyta.json'
    annotations_path = os.path.join(tests_path, annotations_name)
    if os.path.isfile(annotations_path):
        with open(annotations_path) as annotations_open:
            api.upload_annotations(assignment_id, group_id, json.load(annotations_open))
