#!/bin/bash
HERE="$(dirname "$(realpath "$0")")"
SUBNET_CHECK="las las" exec "$HERE/../home_screen/launch_home.sh" "$HERE/las_home.py" "$@"
