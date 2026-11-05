"""
v2 LAS home screen: the lasdev style (floor plan + TabDock) driven by the LAS PVs.

The floor plan replaces v1's grid; the rest is arranged like v1 (toolbar under it, dock on the right):

    +-----------------------------------+----------------+
    |   bg.png with clickable bays,     |                |
    |   racks, BTS, and control icons   |   TabDock      |
    |                                   |                |
    | LAS toolbar tabs                  |                |
    +-----------------------------------+----------------+

The toolbar is the full LAS toolbar (same yaml as v1).

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
from qtpy.QtWidgets import QHBoxLayout, QStyle, QVBoxLayout  # noqa: E402

from pcdswidgets.common.dock.tab_dock import TabDock  # noqa: E402
from pcdswidgets.common.toolbar.yaml_toolbar import YamlToolbar  # noqa: E402

DOCK_WIDTH = 850

# Let the BTPS screens' "open device" buttons find v1's las-open-device with the same python.
os.environ["PATH"] = f"{V1_DIR / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}"
os.environ.setdefault("LAS_DEV_PYTHON", sys.executable)


def toolbar_full_height(toolbar: YamlToolbar) -> int:
    """Height at which the tallest YamlToolbar tab shows all its buttons without scrolling."""
    tabs = toolbar.tab
    content = 0
    for index in range(tabs.count()):
        scroll_area = tabs.widget(index)
        page = scroll_area.widget()
        content = max(content, page.sizeHint().height() + 2 * scroll_area.frameWidth())
    pane_frame = 2 * tabs.style().pixelMetric(QStyle.PM_DefaultFrameWidth, None, tabs)
    margins = toolbar.layout().contentsMargins()
    return content + tabs.tabBar().sizeHint().height() + pane_frame + margins.top() + margins.bottom()


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

        self.floorplan = FloorPlan(self.context)
        self.toolbar = YamlToolbar()
        self.toolbar.filename = toolbar_file
        # Tall enough that no toolbar tab needs to scroll; the floor plan has its own minimum,
        # so the window minimum ends up fitting both.
        self.toolbar.setMinimumHeight(toolbar_full_height(self.toolbar))

        # Floor plan takes the spare height, the toolbar sits under it at its natural size
        self.left_vlayout = QVBoxLayout()
        self.left_vlayout.setContentsMargins(0, 0, 0, 0)
        self.left_vlayout.addWidget(self.floorplan, stretch=1)
        self.left_vlayout.addWidget(self.toolbar)

        self.dock = TabDock()
        self.dock.set_fixed_tab_width(DOCK_WIDTH)

        layout = QHBoxLayout()
        layout.setContentsMargins(3, 3, 3, 3)
        layout.addLayout(self.left_vlayout, stretch=1)
        layout.addWidget(self.dock)
        self.setLayout(layout)
