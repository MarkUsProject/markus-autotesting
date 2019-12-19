#!/usr/bin/env bash

set -e

create_venv() {
    rm -rf ${VENV_DIR} # clean up existing venv if any
    python${PY_VERSION} -m venv ${VENV_DIR}
    source ${VENV_DIR}/bin/activate
    pip install --upgrade pip
    pip install wheel
    pip install -r "${THIS_DIR}/requirements.txt"
    pip install -r <(echo ${PIP_REQUIREMENTS} | sed 's/\s\+/\n/g') # sub spaces for newlines
    local pth_file=${VENV_DIR}/lib/python${PY_VERSION}/site-packages/lib.pth
    echo ${LIB_DIR} >> ${pth_file}
    echo ${TESTERS_DIR} >> ${pth_file}
}

# script starts here
if [[ $# -lt 1 ]]; then
    echo "Usage: $0 settings_json"
fi
   
# vars
SETTINGS_JSON=$1

ENV_DIR=$(echo ${SETTINGS_JSON} | jq --raw-output .env_loc)
PY_VERSION=$(echo ${SETTINGS_JSON} | jq --raw-output .env_data.python_version)
PIP_REQUIREMENTS=$(echo ${SETTINGS_JSON} | jq --raw-output .env_data.pip_requirements)

VENV_DIR=${ENV_DIR}/venv
THIS_SCRIPT=$(readlink -f ${BASH_SOURCE})
THIS_DIR=$(dirname ${THIS_SCRIPT})
LIB_DIR=$(readlink -f ${THIS_DIR}/../lib)
TESTERS_DIR=$(readlink -f ${THIS_DIR}/../../../)

# main
create_venv
