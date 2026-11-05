#!/bin/bash
# shellcheck disable=SC1091
# Dev launcher for the v2 (floor plan) LAS home screen.
#
# Same environment as v1 (dev/v1/las_home.sh): shared ctrlenv-widgets pixi env, this checkout's
# pcdswidgets first on PYTHONPATH, nothing installed or modified. v2 reuses v1's device list,
# device screens, and toolbar, so dev/v1 is on PYTHONPATH too.
#
# Usage: dev/v2/las_home.sh [extra pydm args]
# Env overrides:
#   ENVVER         ctrlenv-widgets version (default v1.2.1, the version this was tested with)
#   LAS_DEVICE_DB  happi JSON database or YAML snapshot (default: path in $HAPPI_CFG)

V2_DIR="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
V1_DIR="$(dirname "${V2_DIR}")/v1"
REPO_DIR="$(dirname "$(dirname "${V2_DIR}")")"
ENVVER="${ENVVER:-v1.2.1}"

unset PYTHONPATH
source /cds/group/pcds/engineering_tools/latest-released/scripts/ctrlenv_setup.sh
ctrlenv-activate ctrlenv-widgets/"${ENVVER}" || exit 1

if type subnet_check &>/dev/null; then
    subnet_check las las
fi

export PYTHONPATH="${REPO_DIR}:${V2_DIR}:${V1_DIR}"
export PATH="${V1_DIR}/bin:${PATH}"
export LAS_DEV_PYTHON="$(command -v python)"

pydm --hide-nav-bar --hide-menu-bar --hide-status-bar "$@" "${V2_DIR}/las_home.py" &
