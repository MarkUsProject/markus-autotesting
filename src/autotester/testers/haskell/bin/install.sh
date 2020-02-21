#!/usr/bin/env bash

set -e

install_packages() {
    echo "[HASKELL-INSTALL] Installing system packages"
    local debian_frontend
    local apt_opts
    local apt_yes
    if [ -n "${NON_INTERACTIVE}" ]; then
      debian_frontend=noninteractive
      apt_opts=(-o 'Dpkg::Options::=--force-confdef' -o 'Dpkg::Options::=--force-confold')
      apt_yes='-y'
    fi
    sudo DEBIAN_FRONTEND=${debian_frontend} apt-get ${apt_yes} "${apt_opts[@]}" install ghc cabal-install
}

install_haskell_packages() {
    sudo cabal update
    # The order that these packages are installed matters. Could cause a dependency conflict 
    # Crucially it looks like tasty-stats needs to be installed before tasty-quickcheck 
    # TODO: install these without cabal so they can be properly isolated/uninstalled
    sudo cabal install tasty-stats --global
    sudo cabal install tasty-discover --global
    sudo cabal install tasty-quickcheck --global
}

# script starts here
if [[ $# -gt 1 ]]; then
    echo "Usage: $0 [--non-interactive]"
    exit 1
fi

# vars
THISSCRIPT=$(readlink -f "${BASH_SOURCE[0]}")
THISDIR=$(dirname "${THISSCRIPT}")
SPECSDIR=$(readlink -f "${THISDIR}/../specs")
NON_INTERACTIVE=$1

# main
install_packages
install_haskell_packages
touch "${SPECSDIR}/.installed"
