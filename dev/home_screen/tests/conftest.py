"""
Core tests only: config, device data and command parsing. No widget is created or shown, so no Qt
application is needed.
"""

import os
import sys
from pathlib import Path

import pytest
import yaml

# Keep channel access searches on this machine: the tests never need a live IOC.
os.environ["EPICS_CA_AUTO_ADDR_LIST"] = "NO"
os.environ["EPICS_CA_ADDR_LIST"] = "127.0.0.1"

# Only this package is added here; pcdswidgets comes from PYTHONPATH (a checkout) or the environment.
PACKAGE_DIR = Path(__file__).resolve().parent.parent
if str(PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_DIR))

# Every location that uses the package: each dev/<location> with a config/floorplan.yaml
LOCATIONS = sorted(path.parent.parent for path in PACKAGE_DIR.parent.glob("*/config/floorplan.yaml"))
# A dated snapshot of each location's active happi devices (tools/export_happi_devices.py), used instead of happi
SNAPSHOTS = PACKAGE_DIR / "tests" / "snapshots"


def snapshot(location: Path) -> Path:
    return SNAPSHOTS / f"{location.name}.yaml"


def floorplan_config(location: Path) -> dict:
    return yaml.safe_load((location / "config" / "floorplan.yaml").read_text())


@pytest.fixture(params=LOCATIONS, ids=lambda path: path.name)
def location(request) -> Path:
    return request.param


@pytest.fixture
def context(location: Path):
    """The location's FloorPlanContext with its snapshot: builds every opener, but no widget."""
    from floorplan import FloorPlanContext

    return FloorPlanContext(config_file=location / "config" / "floorplan.yaml", device_db=snapshot(location))


@pytest.fixture(autouse=True)
def no_external_commands(monkeypatch):
    """Never launch EDM or other external tools from the tests."""
    import floorplan

    launched = []
    monkeypatch.setattr(floorplan, "run_command", lambda commands: launched.extend(commands))
    return launched
