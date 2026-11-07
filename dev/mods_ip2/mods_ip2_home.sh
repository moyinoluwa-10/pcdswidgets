#!/bin/bash
HERE="$(dirname "$(realpath "$0")")"
SUBNET_CHECK="ip2 las tmo" exec "$HERE/../home_screen/launch_home.sh" "$HERE/mods_ip2_home.py" "$@"
