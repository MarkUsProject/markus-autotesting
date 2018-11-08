#!/usr/bin/env bash

install_packages() {
    echo "[RACKET] Installing system packages"
    sudo apt-get install racket
}

# script starts here
if [ $# -ne 0 ]; then
    echo "Usage: $0"
    exit 1
fi

# main
install_packages
