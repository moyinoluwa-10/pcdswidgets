import os
import sys
from pathlib import Path

import pytest

# Keep channel access searches on this machine: the tests never need a live IOC.
# These must be set before pyepics creates its CA context.
os.environ["EPICS_CA_AUTO_ADDR_LIST"] = "NO"
os.environ["EPICS_CA_ADDR_LIST"] = "127.0.0.1"

V2_DIR = Path(__file__).resolve().parent.parent
V1_DIR = V2_DIR.parent / "v1"
REPO_DIR = V2_DIR.parents[1]
for path in (str(V1_DIR), str(V2_DIR), str(REPO_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

SNAPSHOT = V1_DIR / "config" / "las_devices.yaml"


@pytest.fixture(autouse=True)
def snapshot_db(monkeypatch):
    """Use v1's committed YAML snapshot instead of the live happi database."""
    monkeypatch.setenv("LAS_DEVICE_DB", str(SNAPSHOT))
    return SNAPSHOT


@pytest.fixture(autouse=True)
def no_external_commands(monkeypatch):
    """Never launch EDM or other external tools from the tests."""
    import floorplan

    launched = []
    monkeypatch.setattr(floorplan, "run_command", lambda commands: launched.extend(commands))
    return launched
