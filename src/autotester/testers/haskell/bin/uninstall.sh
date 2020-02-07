#!/usr/bin/env bash

# script starts here
if [[ $# -ne 0 ]]; then
    echo "Usage: $0"
    exit 1
fi

# vars
THISSCRIPT=$(readlink -f "${BASH_SOURCE[0]}")
THISDIR=$(dirname "${THISSCRIPT}")
SPECSDIR=$(readlink -f "${THISDIR}/../specs")

# main
echo "[HASKELL-UNINSTALL] The following system packages have not been uninstalled: ghc cabal-install python3. You may uninstall them if you wish."
echo "[HASKELL-UNINSTALL] The following cabal packages have not been uninstalled: tasty-stats tasty-discover tasty-quickcheck. You may uninstall them if you can figure out how."
rm -f "${SPECSDIR}/.installed"
