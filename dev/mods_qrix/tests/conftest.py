import os
import sys
from pathlib import Path

import pytest

# Keep channel access searches on this machine: the tests never need a live IOC.
# These must be set before pyepics creates its CA context.
os.environ["EPICS_CA_AUTO_ADDR_LIST"] = "NO"
os.environ["EPICS_CA_ADDR_LIST"] = "127.0.0.1"

# This location is its config (floorplan.yaml, toolbar); the screen is the shared dev/home_screen package.
# Only the package is added here; pcdswidgets comes from PYTHONPATH (a checkout) or the environment.
APP_DIR = Path(__file__).resolve().parent.parent
PACKAGE_DIR = APP_DIR.parent / "home_screen"
if str(PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_DIR))

SNAPSHOT = APP_DIR / "tests" / "devices_snapshot.yaml"
FLOORPLAN = APP_DIR / "config" / "floorplan.yaml"


@pytest.fixture(autouse=True)
def location(monkeypatch):
    """This location's floorplan.yaml, and the committed YAML snapshot instead of the live happi database."""
    monkeypatch.setenv("HOME_FLOORPLAN", str(FLOORPLAN))
    monkeypatch.setenv("HOME_DEVICE_DB", str(SNAPSHOT))
    return FLOORPLAN


@pytest.fixture(autouse=True)
def no_external_commands(monkeypatch):
    """Never launch EDM or other external tools from the tests."""
    import floorplan

    launched = []
    monkeypatch.setattr(floorplan, "run_command", lambda commands: launched.extend(commands))
    return launched
