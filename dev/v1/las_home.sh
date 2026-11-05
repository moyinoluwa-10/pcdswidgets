#!/bin/bash
# shellcheck disable=SC1091
# Dev launcher for the v1 LAS home screen: a LUCID look-alike (device grid + toolbar + TabDock) on pcdswidgets.
#
# Shared ctrlenv-widgets pixi env, with this checkout's pcdswidgets and dev/v1 first on PYTHONPATH.
# Nothing is installed or modified. Standalone: needs nothing else from dev/.
# This is the dev equivalent of "Option 4: pydm home with pixi" in /reg/g/pcds/pyps/config/las/las_home.sh.
#
# Usage: dev/v1/las_home.sh [extra pydm args]     (runs in the foreground; add "&" to get the terminal back)
#   e.g. the live toolbar: dev/v1/las_home.sh -m '{"TOOLBAR": "/cds/group/pcds/pyps/apps/hutch-python/lucid_config/LAS_toolbar.yaml"}'
# Env overrides:
#   ENVVER           ctrlenv-widgets version (default v1.2.1, the version this was tested with)
#   LAS_DEVICE_DB    happi JSON database or YAML snapshot (default: path in $HAPPI_CFG)
#   PCDSWIDGETS_DIR  pcdswidgets checkout to put first on PYTHONPATH (default: ../.. from here)

APP_DIR="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
REPO_DIR="${PCDSWIDGETS_DIR:-$(dirname "$(dirname "${APP_DIR}")")}"
ENVVER="${ENVVER:-v1.2.1}"

unset PYTHONPATH
source /cds/group/pcds/engineering_tools/latest-released/scripts/ctrlenv_setup.sh
ctrlenv-activate ctrlenv-widgets/"${ENVVER}" || exit 1

# Same check as the `las` shell function
if type subnet_check &>/dev/null; then
    subnet_check las las
fi

export PYTHONPATH="${REPO_DIR}:${APP_DIR}"
# The BTPS screens' "open device" buttons run bin/las-open-device, with the same python as this pydm
export PATH="${APP_DIR}/bin:${PATH}"
LAS_DEV_PYTHON="$(command -v python)"
export LAS_DEV_PYTHON

exec pydm --hide-nav-bar --hide-menu-bar --hide-status-bar "$@" "${APP_DIR}/las_home.py"
