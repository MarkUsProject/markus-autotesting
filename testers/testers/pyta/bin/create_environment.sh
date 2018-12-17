#!/usr/bin/env bash

set -e

create_venv() {
    rm -rf ${VENVDIR} # clean up existing venv if any
    python${PYVERSION} -m venv ${VENVDIR}
    source ${VENVDIR}/bin/activate
    pip install wheel
    for req in ${PIPREQUIREMENTS}
    do
        pip install ${req}
    done
}

get_setting() {
    echo ${JSONSETTINGS} | python3 -c "import sys, json; print(json.load(sys.stdin)['$1'])"
}

get_default_setting() {
    cat ${DEFAULTSETTINGS} | python3 -c "import sys, json; print(json.load(sys.stdin)['$1'])"
}

# script starts here
if [[ $# -lt 3 ]]; then
    echo "Usage: $0 working_specs_dir tester_name settings_json"
    exit 1
fi

# vars
WORKINGSPECSDIR=$(readlink -f $1)
TESTERNAME=$2
JSONSETTINGS=$3

THISSCRIPT=$(readlink -f ${BASH_SOURCE})
BINDIR=$(dirname ${THISSCRIPT})
SPECSDIR=$(dirname ${BINDIR})/specs
DEFAULTSETTINGS=${SPECSDIR}/default_environment_settings.json

VENVDIR=${WORKINGSPECSDIR}/${TESTERNAME}/venv
PYVERSION=$(get_setting python_version)
PIPREQUIREMENTS="$(get_default_setting pip_requirements) $(get_setting pip_requirements)"

create_venv

