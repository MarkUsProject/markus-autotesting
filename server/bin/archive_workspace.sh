#!/usr/bin/env bash

archive() {
	local archivename="$(basename ${WORKSPACEDIR}).tar.gz"
	local archivefile="${ARCHIVEDIR}/${archivename}"
	echo "[AUTOTEST-ARCHIVE] archiving ${WORKSPACEDIR} as ${archivefile}"
	if [[ -f ${archivefile} ]] {
		echo "${archivefile} already exists, cannot ovewrite existing archive"
		exit
	}
	tar cJf ${ARCHIVEDIR} ${WORKSPACEDIR}
}

get_config_param() {
    echo $(cd ${SERVERDIR} && python3 -c "import config; print(config.$1)")
}

# script starts here
if [ $# -lt 1 ]; then
	echo "Usage: $0 archive_dir"
	exit 1
fi

# vars
THISSCRIPT=$(readlink -f ${BASH_SOURCE})
BINDIR=$(dirname ${THISSCRIPT})
SERVERDIR=$(dirname ${BINDIR})
WORKSPACEDIR=$(get_config_param WORKSPACE_DIR)
ARCHIVEDIR=$1

archive