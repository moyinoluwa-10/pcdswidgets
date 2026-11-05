"""
Export a beamline's active happi devices to a YAML snapshot, without importing happi.

The home screen reads the live happi JSON database by default. A snapshot is
useful for testing offline, or for pinning the device list while the database changes.
The snapshot is always taken from happi ($HAPPI_CFG), never from $MODS_QRIX_DEVICE_DB.
Runs with any python that has PyYAML.

Usage::

    python dev/mods_qrix/tools/export_happi_devices.py QRIX_MODS dev/mods_qrix/tests/devices_snapshot.yaml
    MODS_QRIX_DEVICE_DB=dev/mods_qrix/tests/devices_snapshot.yaml dev/mods_qrix/mods_qrix_home.sh
"""

import argparse
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from devices import happi_database_path, load_devices


def main():
    parser = argparse.ArgumentParser(description="Export active happi devices for a beamline to YAML.")
    parser.add_argument("beamline")
    parser.add_argument("output")
    parser.add_argument("--database", default=None, help="happi JSON database (default: the path in $HAPPI_CFG)")
    args = parser.parse_args()
    print(f"Exporting active happi devices for {args.beamline} to {args.output}")

    database = args.database or happi_database_path()
    devices = sorted(load_devices(args.beamline, database), key=lambda dev: dev.name)
    with open(args.output, "w") as fd:
        fd.write(f"# Snapshot of active {args.beamline} devices from {database}, taken {date.today().isoformat()}\n")
        fd.write(f"# Regenerate with: python dev/mods_qrix/tools/export_happi_devices.py {args.beamline} <this file>\n")
        yaml.safe_dump([asdict(dev) for dev in devices], fd, sort_keys=False)


if __name__ == "__main__":
    main()
