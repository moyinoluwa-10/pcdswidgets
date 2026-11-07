#!/bin/bash
# Dev launcher for the IP2 MODS floor-plan home screen, the pcdswidgets take on `mods_ip2`.
#
# The screen itself is dev/home_screen (shared by every location); this location is config/floorplan.yaml
# (drawing, beamline, title) and its toolbar. Nothing is installed or modified.
#
# Usage: dev/mods_ip2/mods_ip2_home.sh [extra pydm args]     (runs in the foreground; add "&" to get the terminal back)
#   e.g. the live toolbar: dev/mods_ip2/mods_ip2_home.sh -m '{"TOOLBAR": "/cds/group/pcds/pyps/apps/hutch-python/lucid_config/IP2_MODS_toolbar.yaml"}'
# Env overrides (see dev/home_screen/launch_home.sh): ENVVER, HOME_DEVICE_DB, PCDSWIDGETS_DIR,
#   HOME_SCREEN_DIR  the home_screen package (default: ../home_screen from here)

HERE="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
# Same check as the `mods_ip2` shell function
export SUBNET_CHECK="ip2 las tmo"
exec "${HOME_SCREEN_DIR:-${HERE}/../home_screen}/launch_home.sh" "${HERE}/config/floorplan.yaml" "$@"
