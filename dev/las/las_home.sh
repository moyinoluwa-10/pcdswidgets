#!/bin/bash
# Dev launcher for the LAS floor-plan home screen, the pcdswidgets take on `las`.
#
# The screen itself is dev/home_screen (shared by every location); this location is config/floorplan.yaml
# (drawing, beamline, title) and its toolbar. Nothing is installed or modified.
#
# Usage: dev/las/las_home.sh [extra pydm args]     (runs in the foreground; add "&" to get the terminal back)
#   e.g. the live toolbar: dev/las/las_home.sh -m '{"TOOLBAR": "/cds/group/pcds/pyps/apps/hutch-python/lucid_config/LAS_toolbar.yaml"}'
# Env overrides (see dev/home_screen/launch_home.sh): ENVVER, HOME_DEVICE_DB, PCDSWIDGETS_DIR,
#   HOME_SCREEN_DIR  the home_screen package (default: ../home_screen from here)

HERE="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
# Same check as the `las` shell function
export SUBNET_CHECK="las las"
exec "${HOME_SCREEN_DIR:-${HERE}/../home_screen}/launch_home.sh" "${HERE}/config/floorplan.yaml" "$@"
