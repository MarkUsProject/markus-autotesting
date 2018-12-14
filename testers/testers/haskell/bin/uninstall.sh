#!/usr/bin/env bash

echo "[HASKELL-UNINSTALL] the following system packages have not been uninstalled: ghc cabal-install python3. You may now uninstall them if you wish"
echo "[HASKELL-UNINSTALL] the following cabal packages have not been uninstalled: tasty-stats tasty-discover tasty-quickcheck. You may now uninstall them if you can figure out how"

THISSCRIPT=$(readlink -f ${BASH_SOURCE})
TESTERDIR=$(dirname $(dirname ${THISSCRIPT}))
SPECSDIR=${TESTERDIR}/specs

rm ${SPECSDIR}/.installed
