import os
import sys
from pathlib import Path

# Keep channel access searches on this machine: the tests never need a live IOC.
# These must be set before pyepics creates its CA context.
os.environ["EPICS_CA_AUTO_ADDR_LIST"] = "NO"
os.environ["EPICS_CA_ADDR_LIST"] = "127.0.0.1"

# Only this package is added here; pcdswidgets comes from PYTHONPATH (a checkout) or the environment.
PACKAGE_DIR = Path(__file__).resolve().parent.parent
if str(PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_DIR))
