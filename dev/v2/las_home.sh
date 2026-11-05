#!/bin/bash
# shellcheck disable=SC1091
# Dev launcher for the v2 (floor plan) LAS home screen.
#
# Shared ctrlenv-widgets pixi env, with this checkout's pcdswidgets and dev/v2 first on PYTHONPATH.
# Nothing is installed or modified. Standalone: dev/v2 needs nothing from dev/v1.
#
# Usage: dev/v2/las_home.sh [extra pydm args]
# Env overrides:
#   ENVVER         ctrlenv-widgets version (default v1.2.1, the version this was tested with)
#   LAS_DEVICE_DB  happi JSON database or YAML snapshot (default: path in $HAPPI_CFG)
#   PCDSWIDGETS_DIR  pcdswidgets checkout to put first on PYTHONPATH (default: ../.. from here)

V2_DIR="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
# pcdswidgets checkout to use (default: the one this directory lives in, pcdswidgets/dev/v2)
REPO_DIR="${PCDSWIDGETS_DIR:-$(dirname "$(dirname "${V2_DIR}")")}"
ENVVER="${ENVVER:-v1.2.1}"

unset PYTHONPATH
source /cds/group/pcds/engineering_tools/latest-released/scripts/ctrlenv_setup.sh
ctrlenv-activate ctrlenv-widgets/"${ENVVER}" || exit 1

if type subnet_check &>/dev/null; then
    subnet_check las las
fi

export PYTHONPATH="${REPO_DIR}:${V2_DIR}"

pydm --hide-nav-bar --hide-menu-bar --hide-status-bar "$@" "${V2_DIR}/las_home.py" &
