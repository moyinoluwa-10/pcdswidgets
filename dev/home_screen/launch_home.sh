#!/bin/bash
# shellcheck disable=SC1091
# Dev launcher for a floor-plan home screen: dev/home_screen/home.py with a location's floorplan.yaml.
#
# Shared ctrlenv-widgets pixi env, with this checkout's pcdswidgets and dev/home_screen first on PYTHONPATH.
# Nothing is installed or modified. Each location's launcher (e.g. dev/las/las_home.sh) calls this.
#
# Usage: dev/home_screen/launch_home.sh <floorplan.yaml> [extra pydm args]     (runs in the foreground)
#   e.g. the live toolbar: ... -m '{"TOOLBAR": "/cds/group/pcds/pyps/apps/hutch-python/lucid_config/LAS_toolbar.yaml"}'
# Env:
#   SUBNET_CHECK     arguments for subnet_check, e.g. "las las" (the location's launcher sets it; empty: no check)
#   ENVVER           ctrlenv-widgets version (default v1.2.1, the version this was tested with)
#   HOME_DEVICE_DB   happi JSON database or YAML snapshot (default: path in $HAPPI_CFG)
#   PCDSWIDGETS_DIR  pcdswidgets checkout to put first on PYTHONPATH (default: ../.. from here)

if [ $# -lt 1 ]; then
    echo "Usage: $0 <floorplan.yaml> [extra pydm args]" >&2
    exit 2
fi
FLOORPLAN="$(realpath "$1")"
shift

PACKAGE_DIR="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
REPO_DIR="${PCDSWIDGETS_DIR:-$(dirname "$(dirname "${PACKAGE_DIR}")")}"
ENVVER="${ENVVER:-v1.2.1}"

unset PYTHONPATH
source /cds/group/pcds/engineering_tools/latest-released/scripts/ctrlenv_setup.sh
ctrlenv-activate ctrlenv-widgets/"${ENVVER}" || exit 1

# Same read-only / write-enabled message as the location's shell function (e.g. `las`, `mods_ip1`)
if [ -n "${SUBNET_CHECK}" ] && type subnet_check &>/dev/null; then
    # shellcheck disable=SC2086
    subnet_check ${SUBNET_CHECK}
fi

export PYTHONPATH="${REPO_DIR}:${PACKAGE_DIR}"
export HOME_FLOORPLAN="${FLOORPLAN}"

exec pydm --hide-nav-bar --hide-menu-bar --hide-status-bar "$@" "${PACKAGE_DIR}/home.py"
