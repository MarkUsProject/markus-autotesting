#!/usr/bin/env bash

set -e

archive_workspace() {
    local archivename="$(basename ${WORKSPACEDIR}).tar.xz"
    local archivefile="${ARCHIVEDIR}/${archivename}"

    echo "[AUTOTEST-ARCHIVE] Archiving '${WORKSPACEDIR}' at '${archivefile}'"
    pushd ${WORKSPACEDIR} > /dev/null
    tar cJf ${archivefile} .
    popd > /dev/null
}

get_config_param() {
    echo $(cd ${SERVERDIR} && python3 -c "import config; print(config.$1)")
}

# script starts here
if [[ $# -lt 1 ]]; then
    echo "Usage: $0 archive_dir"
    exit 1
fi

# vars
THISSCRIPT=$(readlink -f ${BASH_SOURCE})
BINDIR=$(dirname ${THISSCRIPT})
SERVERDIR=$(dirname ${BINDIR})
WORKSPACEDIR=$(get_config_param WORKSPACE_DIR)
ARCHIVEDIR=$(readlink -f $1)

archive_workspace
