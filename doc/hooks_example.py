import glob
import os
import json
import shutil
import subprocess


# Helper functions
def upload_svn_file(
    api,
    group_repo_name,
    assignment_name,
    file_name,
    svn_user,
    svn_password,
    commit_message,
):
    repo_url = f"{api.parsed_url.scheme}://{api.parsed_url.netloc}/svn{api.parsed_url.path}/{group_repo_name}"
    svn_co_command = [
        "svn",
        "co",
        "--username",
        svn_user,
        "--password",
        svn_password,
        repo_url,
    ]
    subprocess.run(svn_co_command, capture_output=True, check=True)
    repo_file_path = os.path.join(group_repo_name, assignment_name, file_name)
    previous_file = os.path.isfile(repo_file_path)
    shutil.copy2(file_name, repo_file_path)
    if not previous_file:
        svn_add_command = ["svn", "add", repo_file_path]
        subprocess.run(svn_add_command, capture_output=True, check=True)
    svn_ci_command = [
        "svn",
        "ci",
        "--username",
        svn_user,
        "--password",
        svn_password,
        "-m",
        commit_message,
        repo_file_path,
    ]
    subprocess.run(svn_ci_command, capture_output=True, check=True)


# Hooks
def before_all(_api, _assignment_id, _group_id, _group_repo_name):
    # clean up unwanted files
    pattern = os.path.join("**", "*.o")
    for file_path in glob.glob(pattern, recursive=True):
        os.remove(file_path)


def before_each(_api, _assignment_id, _group_id, _group_repo_name):
    pass


def after_each(_api, _assignment_id, _group_id, _group_repo_name):
    pass


def after_all(api, assignment_id, group_id, group_repo_name):
    # upload feedback file
    feedback_name = "feedback_pyta.txt"
    if os.path.isfile(feedback_name):
        with open(feedback_name) as feedback_open:
            api.upload_feedback_file(
                assignment_id, group_id, feedback_name, feedback_open.read()
            )
            # upload in svn repo
            upload_svn_file(
                api,
                group_repo_name,
                "AX",
                feedback_name,
                "svn_user",
                "svn_password",
                "Feedback file",
            )
    # upload annotations
    annotations_name = "feedback_pyta.json"
    if os.path.isfile(annotations_name):
        with open(annotations_name) as annotations_open:
            api.upload_annotations(assignment_id, group_id, json.load(annotations_open))
