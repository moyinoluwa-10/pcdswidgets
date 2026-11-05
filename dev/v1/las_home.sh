#!/bin/bash
# shellcheck disable=SC1091
# Dev launcher for the pcdswidgets LAS home screen.
#
# This is the dev equivalent of "Option 4: pydm home with pixi" in
# /reg/g/pcds/pyps/config/las/las_home.sh, but it only reads shared files:
# the pixi env is activated in this process, and this checkout's pcdswidgets
# and dev/ code are put first on PYTHONPATH.
#
# Usage: dev/v1/las_home.sh [extra pydm args]
# Env overrides:
#   ENVVER         ctrlenv-widgets version (default v1.2.1, the version this was tested with)
#   LAS_DEVICE_DB  happi JSON database or YAML snapshot (default: path in $HAPPI_CFG)

DEV_DIR="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
REPO_DIR="$(dirname "$(dirname "${DEV_DIR}")")"
ENVVER="${ENVVER:-v1.2.1}"

unset PYTHONPATH
source /cds/group/pcds/engineering_tools/latest-released/scripts/ctrlenv_setup.sh
ctrlenv-activate ctrlenv-widgets/"${ENVVER}" || exit 1

if type subnet_check &>/dev/null; then
    subnet_check las las
fi

export PYTHONPATH="${REPO_DIR}:${DEV_DIR}"
export PATH="${DEV_DIR}/bin:${PATH}"
export LAS_DEV_PYTHON="$(command -v python)"

pydm --hide-nav-bar --hide-menu-bar --hide-status-bar "$@" "${DEV_DIR}/las_home.py" &
