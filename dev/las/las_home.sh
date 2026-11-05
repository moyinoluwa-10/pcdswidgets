#!/bin/bash
# shellcheck disable=SC1091
# Dev launcher for the LAS floor-plan home screen.
#
# Shared ctrlenv-widgets pixi env, with this checkout's pcdswidgets and dev/las first on PYTHONPATH.
# Nothing is installed or modified. Standalone: needs nothing else from dev/.
#
# Usage: dev/las/las_home.sh [extra pydm args]     (runs in the foreground; add "&" to get the terminal back)
#   e.g. the live toolbar: dev/las/las_home.sh -m '{"TOOLBAR": "/cds/group/pcds/pyps/apps/hutch-python/lucid_config/LAS_toolbar.yaml"}'
# Env overrides:
#   ENVVER         ctrlenv-widgets version (default v1.2.1, the version this was tested with)
#   LAS_DEVICE_DB  happi JSON database or YAML snapshot (default: path in $HAPPI_CFG)
#   PCDSWIDGETS_DIR  pcdswidgets checkout to put first on PYTHONPATH (default: ../.. from here)

LAS_DIR="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
REPO_DIR="${PCDSWIDGETS_DIR:-$(dirname "$(dirname "${LAS_DIR}")")}"
ENVVER="${ENVVER:-v1.2.1}"

unset PYTHONPATH
source /cds/group/pcds/engineering_tools/latest-released/scripts/ctrlenv_setup.sh
ctrlenv-activate ctrlenv-widgets/"${ENVVER}" || exit 1

if type subnet_check &>/dev/null; then
    subnet_check las las
fi

export PYTHONPATH="${REPO_DIR}:${LAS_DIR}"

exec pydm --hide-nav-bar --hide-menu-bar --hide-status-bar "$@" "${LAS_DIR}/las_home.py"
