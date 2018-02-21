#!/usr/bin/env bash

check_tester_existence() {
    if [[ ! -d ${TESTERDIR} ]]; then
        echo "[ENV] The tester '${TESTERNAME}' does not exist"
        exit 1
    fi
}

install_packages() {
    echo "[ENV] Installing system packages"
    sudo apt-get install python3 python3-venv
}

create_specs() {
    echo "[ENV] Creating specs directory '${SPECSDIR}'"
    rm -rf ${SPECSDIR} # clean up existing specs if any
    mkdir -p ${SPECSDIR}
    if [[ -e ${WORKINGDIR}/specs.json ]]; then
        mv ${WORKINGDIR}/specs.json ${SPECSDIR}
    else
        cp ${TESTERDIR}/specs.json ${SPECSDIR}
    fi
}

init_specs() {
    if [[ -e ${TESTERDIR}/init_specs.sh ]]; then
        echo "[ENV] Initializing specs"
        ${TESTERDIR}/init_specs.sh ${WORKINGDIR} ${SPECSDIR}
    fi
}

create_venv() {
    echo "[ENV] Creating virtualenv '${VENVDIR}'"
    rm -rf ${VENVDIR} # clean up existing venv if any
    python${PYVERSION} -m venv ${VENVDIR}
    source ${VENVDIR}/bin/activate
    pip install wheel
    if [[ -e ${TESTERDIR}/requirements.txt ]]; then
        pip install -r ${TESTERDIR}/requirements.txt
    fi
    echo "${TESTERDIR}/server" > ${VENVDIR}/lib/python${PYVERSION}/site-packages/markus_${TESTERNAME}.pth
    echo "${THISSCRIPTDIR}" > ${VENVDIR}/lib/python${PYVERSION}/site-packages/markus.pth
}

suggest_next_steps() {
    echo "[ENV] (You must use this shebang in your test scripts: '#!${VENVDIR}/bin/python3')"
}

# script starts here
if [[ $# -lt 4 || $# -gt 5 ]]; then
    echo "Usage: $0 autotest_working_dir tester_name python_version course_name [env_name]"
    exit 1
fi

# vars
THISSCRIPT=$(readlink -f ${BASH_SOURCE})
THISSCRIPTDIR=$(dirname ${THISSCRIPT})
WORKINGDIR=$(readlink -f $1)
TESTERNAME=$2
PYVERSION=$3
COURSENAME=$4
TESTERDIR=${THISSCRIPTDIR}/${TESTERNAME}
SPECSDIR=${WORKINGDIR}/specs/${COURSENAME}
VENVDIR=${WORKINGDIR}/venvs/${COURSENAME}
if [[ $# -eq 5 ]]; then
    ENVNAME=$5
    SPECSDIR=${SPECSDIR}/${ENVNAME}
    VENVDIR=${VENVDIR}/${ENVNAME}
fi

# main
check_tester_existence
install_packages
create_specs
init_specs
create_venv
suggest_next_steps
