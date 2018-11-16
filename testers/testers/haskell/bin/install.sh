#!/usr/bin/env bash

install_packages() {
    echo "[HASKELL] Installing system packages"
    sudo apt-get install ghc cabal-install python3
}

install_haskell_packages() {
    sudo cabal update
    # The order that these packages are installed matters. Could cause a dependency conflict 
    # Crucially it looks like tasty-stats needs to be installed before tasty-quickcheck 
    sudo cabal install tasty-stats --global
    sudo cabal install tasty-discover --global
    sudo cabal install tasty-quickcheck --global
}

# script starts here
if [ $# -ne 0 ]; then
    echo "Usage: $0"
    exit 1
fi

THISSCRIPT=$(readlink -f ${BASH_SOURCE})
TESTERDIR=$(dirname $(dirname ${THISSCRIPT}))
SPECSDIR=${TESTERDIR}/specs

# main
install_packages
install_haskell_packages
touch ${SPECSDIR}/.installed
