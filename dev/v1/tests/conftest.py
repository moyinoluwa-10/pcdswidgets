import os
import sys
from pathlib import Path

import pytest

# Keep channel access searches on this machine: the tests never need a live IOC.
# These must be set before pyepics creates its CA context.
os.environ["EPICS_CA_AUTO_ADDR_LIST"] = "NO"
os.environ["EPICS_CA_ADDR_LIST"] = "127.0.0.1"

# Only this directory is added here; pcdswidgets comes from PYTHONPATH (a checkout) or the environment.
APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

SNAPSHOT = APP_DIR / "tests" / "devices_snapshot.yaml"


@pytest.fixture(autouse=True)
def snapshot_db(monkeypatch):
    """Use the committed YAML snapshot instead of the live happi database."""
    monkeypatch.setenv("LAS_DEVICE_DB", str(SNAPSHOT))
    return SNAPSHOT
