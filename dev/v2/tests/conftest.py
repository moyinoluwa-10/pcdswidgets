import os
import sys
from pathlib import Path

import pytest

# Keep channel access searches on this machine: the tests never need a live IOC.
# These must be set before pyepics creates its CA context.
os.environ["EPICS_CA_AUTO_ADDR_LIST"] = "NO"
os.environ["EPICS_CA_ADDR_LIST"] = "127.0.0.1"

# Only this directory is added here; pcdswidgets comes from PYTHONPATH (a checkout) or the environment.
V2_DIR = Path(__file__).resolve().parent.parent
if str(V2_DIR) not in sys.path:
    sys.path.insert(0, str(V2_DIR))

SNAPSHOT = V2_DIR / "config" / "las_devices.yaml"


@pytest.fixture(autouse=True)
def snapshot_db(monkeypatch):
    """Use the committed YAML snapshot instead of the live happi database."""
    monkeypatch.setenv("LAS_DEVICE_DB", str(SNAPSHOT))
    return SNAPSHOT


@pytest.fixture(autouse=True)
def no_external_commands(monkeypatch):
    """Never launch EDM or other external tools from the tests."""
    import floorplan

    launched = []
    monkeypatch.setattr(floorplan, "run_command", lambda commands: launched.extend(commands))
    return launched
