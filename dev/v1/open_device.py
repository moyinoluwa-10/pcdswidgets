"""
Open one device's pcdswidgets screen by its happi name: the happi-free stand-in for ``typhos <name>``.

Usage::

    python dev/v1/open_device.py las_bts_mcs2_01_m1
    las-open-device las_bts_mcs2_01_m1    # same, via dev/v1/bin on PATH (set by las_home.sh)
"""

import argparse
import json
import os
import shutil
import sys

from las_devices import find_device, find_device_type, load_device_types


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Open a device screen by happi name, without happi or typhos.")
    parser.add_argument("name", help="Device name, e.g. las_bts_mcs2_01_m1")
    parser.add_argument("--database", default=None, help="happi JSON database or YAML snapshot")
    parser.add_argument("--print", action="store_true", help="Print the pydm command instead of running it")
    args = parser.parse_args(argv)

    try:
        device = find_device(args.name, args.database)
    except KeyError as exc:
        print(exc.args[0], file=sys.stderr)
        return 1
    dtype = find_device_type(device, load_device_types())
    if dtype is None:
        print(f"No screen is configured for {device.name} ({device.device_class})", file=sys.stderr)
        return 1

    pydm = shutil.which("pydm") or "pydm"
    cmd = [pydm, "--hide-nav-bar", "-m", json.dumps(dtype.macros_for(device)), dtype.screen_path()]
    if args.print:
        print(" ".join(cmd))
        return 0
    os.execvp(cmd[0], cmd)


if __name__ == "__main__":
    sys.exit(main())
