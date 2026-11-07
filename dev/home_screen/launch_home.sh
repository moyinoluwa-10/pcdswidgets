#!/bin/bash
# shellcheck disable=SC1091
# Dev launcher for a location's <location>_home.py: what the org launcher's "Option 4" does, plus this checkout's
# pcdswidgets first on PYTHONPATH and the location's subnet_check. Each location's <location>_home.sh calls it.
#
# Usage: dev/home_screen/launch_home.sh <location>_home.py [extra pydm args]     (runs in the foreground)
# Env:
#   SUBNET_CHECK     arguments for subnet_check, e.g. "las las" (empty: no check)
#   ENVVER           ctrlenv-widgets version (default v1.2.1)
#   HOME_DEVICE_DB   happi JSON database or YAML snapshot (default: path in $HAPPI_CFG)
#   PCDSWIDGETS_DIR  pcdswidgets checkout to put first on PYTHONPATH (default: ../.. from here)

if [ $# -lt 1 ]; then
    echo "Usage: $0 <location>_home.py [extra pydm args]" >&2
    exit 2
fi
DISPLAY_FILE="$(realpath "$1")"
shift

PACKAGE_DIR="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
REPO_DIR="${PCDSWIDGETS_DIR:-$(dirname "$(dirname "${PACKAGE_DIR}")")}"

unset PYTHONPATH
source /cds/group/pcds/engineering_tools/latest-released/scripts/ctrlenv_setup.sh
ctrlenv-activate ctrlenv-widgets/"${ENVVER:-v1.2.1}" || exit 1

if [ -n "${SUBNET_CHECK}" ] && type subnet_check &>/dev/null; then
    # shellcheck disable=SC2086
    subnet_check ${SUBNET_CHECK}
fi

export PYTHONPATH="${REPO_DIR}"
exec pydm --hide-nav-bar --hide-menu-bar --hide-status-bar "$@" "${DISPLAY_FILE}"
