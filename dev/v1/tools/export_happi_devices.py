"""
Export a beamline's active happi devices to a YAML snapshot, without importing happi.

The home screen reads the live happi JSON database by default. A snapshot is
useful for testing offline, or for pinning the grid while the database changes.

Usage::

    python dev/v1/tools/export_happi_devices.py LAS dev/v1/config/las_devices.yaml
    LAS_DEVICE_DB=dev/v1/config/las_devices.yaml dev/v1/las_home.sh
"""

import argparse
import sys
from dataclasses import asdict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from las_devices import default_database_path, load_devices  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Export active happi devices for a beamline to YAML.")
    parser.add_argument("beamline")
    parser.add_argument("output")
    parser.add_argument("--database", default=None, help="happi JSON database (default: from $HAPPI_CFG)")
    args = parser.parse_args()

    database = args.database or default_database_path()
    devices = load_devices(args.beamline, database)
    with open(args.output, "w") as fd:
        fd.write(f"# Snapshot of active {args.beamline} devices from {database}\n")
        fd.write("# Regenerate with dev/v1/tools/export_happi_devices.py\n")
        yaml.safe_dump([asdict(dev) for dev in devices], fd, sort_keys=False)
    print(f"Wrote {len(devices)} devices to {args.output}")


if __name__ == "__main__":
    main()
