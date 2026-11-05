"""
v2 LAS home screen: the lasdev style (floor plan + TabDock) driven by the LAS PVs.

Layout follows /cds/group/pcds/epics-dev/screens/pydm/lasdev/lasdev_home.ui:

    +-----------------------------------+----------------+
    | [Laser Hall] [Other]              |                |
    |                                   |   TabDock      |
    |   bg.png with clickable bays,     |                |
    |   racks, BTS, and control icons   |                |
    +-----------------------------------+----------------+

The "Other" tab holds the full LAS toolbar (same yaml as v1).

Run it with ``dev/v2/las_home.sh``, or directly::

    pydm --hide-nav-bar --hide-menu-bar --hide-status-bar dev/v2/las_home.py

Macros (all optional):
    FLOORPLAN   layout yaml (default: dev/v2/config/floorplan.yaml)
    TOOLBAR     toolbar yaml (default: dev/v1/config/las_toolbar.yaml)
    DEVICE_DB   happi JSON database or YAML snapshot (default: from $LAS_DEVICE_DB / $HAPPI_CFG)
"""

import os
import sys
from pathlib import Path

V2_DIR = Path(__file__).resolve().parent
if str(V2_DIR) not in sys.path:
    sys.path.insert(0, str(V2_DIR))

from floorplan import CONFIG_FILE, TOOLBAR_FILE, V1_DIR, FloorPlan, FloorPlanContext  # noqa: E402
from pydm import Display  # noqa: E402
from qtpy.QtWidgets import QHBoxLayout, QTabWidget  # noqa: E402

from pcdswidgets.common.dock.tab_dock import TabDock  # noqa: E402
from pcdswidgets.common.toolbar.yaml_toolbar import YamlToolbar  # noqa: E402

DOCK_WIDTH = 850

# Let the BTPS screens' "open device" buttons find v1's las-open-device with the same python.
os.environ["PATH"] = f"{V1_DIR / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}"
os.environ.setdefault("LAS_DEV_PYTHON", sys.executable)


class LasHomeV2(Display):
    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros)
        macros = macros or {}
        self.context = FloorPlanContext(
            config_file=macros.get("FLOORPLAN", CONFIG_FILE),
            toolbar_file=macros.get("TOOLBAR", TOOLBAR_FILE),
            device_db=macros.get("DEVICE_DB") or None,
        )
        self.setup_ui(toolbar_file=str(macros.get("TOOLBAR", TOOLBAR_FILE)))

    def ui_filename(self):
        return None

    def setup_ui(self, toolbar_file: str):
        self.setWindowTitle("LAS Home v2 (pcdswidgets dev)")

        self.tabs = QTabWidget()
        self.floorplan = FloorPlan(self.context)
        self.tabs.addTab(self.floorplan, "Laser Hall")
        self.toolbar = YamlToolbar()
        self.toolbar.filename = toolbar_file
        self.tabs.addTab(self.toolbar, "Other")

        self.dock = TabDock()
        self.dock.set_fixed_tab_width(DOCK_WIDTH)

        layout = QHBoxLayout()
        layout.setContentsMargins(3, 3, 3, 3)
        layout.addWidget(self.tabs, stretch=1)
        layout.addWidget(self.dock)
        self.setLayout(layout)
