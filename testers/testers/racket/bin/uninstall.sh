#!/usr/bin/env bash

echo "[RACKET-UNINSTALL] the following system packages have not been uninstalled: racket python3. You may now uninstall them if you wish"

THISSCRIPT=$(readlink -f ${BASH_SOURCE})
TESTERDIR=$(dirname $(dirname ${THISSCRIPT}))
SPECSDIR=${TESTERDIR}/specs

rm ${SPECSDIR}/.installed
