#!/bin/bash
HERE="$(dirname "$(realpath "$0")")"
SUBNET_CHECK="las las" exec "$HERE/../launch_home.sh" "$HERE/example_home.py" "$@"
