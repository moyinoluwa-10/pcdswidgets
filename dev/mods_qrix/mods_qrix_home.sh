#!/bin/bash
# shellcheck disable=SC1091
# Dev launcher for the QRIX MODS (LM1K2) floor-plan home screen, the pcdswidgets take on `mods_qrix`.
#
# Shared ctrlenv-widgets pixi env, with this checkout's pcdswidgets and dev/mods_qrix first on PYTHONPATH.
# Nothing is installed or modified. Standalone: needs nothing else from dev/.
#
# Usage: dev/mods_qrix/mods_qrix_home.sh [extra pydm args]     (runs in the foreground; add "&" to get the terminal back)
#   e.g. the live toolbar: dev/mods_qrix/mods_qrix_home.sh -m '{"TOOLBAR": "/cds/group/pcds/pyps/apps/hutch-python/lucid_config/QRIX_MODS_toolbar.yaml"}'
# Env overrides:
#   ENVVER              ctrlenv-widgets version (default v1.2.1, the version this was tested with)
#   MODS_QRIX_DEVICE_DB  happi JSON database or YAML snapshot (default: path in $HAPPI_CFG)
#   PCDSWIDGETS_DIR     pcdswidgets checkout to put first on PYTHONPATH (default: ../.. from here)

APP_DIR="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
REPO_DIR="${PCDSWIDGETS_DIR:-$(dirname "$(dirname "${APP_DIR}")")}"
ENVVER="${ENVVER:-v1.2.1}"

unset PYTHONPATH
source /cds/group/pcds/engineering_tools/latest-released/scripts/ctrlenv_setup.sh
ctrlenv-activate ctrlenv-widgets/"${ENVVER}" || exit 1

# Same check as the `mods_qrix` shell function: write-enabled from the LAS or RIX subnets
if type subnet_check &>/dev/null; then
    subnet_check qrix las rix
fi

export PYTHONPATH="${REPO_DIR}:${APP_DIR}"

exec pydm --hide-nav-bar --hide-menu-bar --hide-status-bar "$@" "${APP_DIR}/mods_qrix_home.py"
