"""
CRIX MODS (LM2K2) home screen: the lasdev style (floor plan + TabDock) driven by the CRIX_MODS happi devices.

Floor plan on top, toolbar under it, dock on the right:

    +-----------------------------------+----------------+
    |   INJ > COM > HRM > ATM > EJX     |                |
    |   stations with icons             |   TabDock      |
    |-----------------------------------|                |
    |   CRIX_MODS toolbar tabs           |                |
    +-----------------------------------+----------------+

The toolbar is the full CRIX_MODS toolbar (config/crix_mods_toolbar.yaml).

Run it with ``dev/mods_crix/mods_crix_home.sh``, or directly::

    pydm --hide-nav-bar --hide-menu-bar --hide-status-bar dev/mods_crix/mods_crix_home.py

Macros (all optional):
    FLOORPLAN   layout yaml (default: dev/mods_crix/config/floorplan.yaml)
    TOOLBAR     toolbar yaml (default: dev/mods_crix/config/crix_mods_toolbar.yaml)
    DEVICE_DB   happi JSON database or YAML snapshot (default: from $MODS_CRIX_DEVICE_DB / $HAPPI_CFG)
"""

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from floorplan import CONFIG_FILE, TOOLBAR_FILE, FloorPlan, FloorPlanContext  # noqa: E402
from pydm import Display  # noqa: E402
from qtpy.QtWidgets import QHBoxLayout, QStyle, QVBoxLayout  # noqa: E402

from pcdswidgets.common.dock.tab_dock import TabDock  # noqa: E402
from pcdswidgets.common.toolbar.yaml_toolbar import YamlToolbar  # noqa: E402

DOCK_WIDTH = 850


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


class ModsCrixHome(Display):
    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros)
        macros = macros or {}
        toolbar_file = str(macros.get("TOOLBAR", TOOLBAR_FILE))
        self.context = FloorPlanContext(
            config_file=macros.get("FLOORPLAN", CONFIG_FILE),
            toolbar_file=toolbar_file,
            device_db=macros.get("DEVICE_DB") or None,
        )
        self.setup_ui(toolbar_file=toolbar_file)

    def ui_filename(self):
        return None

    def setup_ui(self, toolbar_file: str):
        self.setWindowTitle("CRIX MODS Home (pcdswidgets dev)")

        self.floorplan = FloorPlan(self.context)
        self.toolbar = YamlToolbar()
        self.toolbar.filename = toolbar_file
        # Tall enough that no toolbar tab needs to scroll
        self.toolbar.setMinimumHeight(toolbar_full_height(self.toolbar))

        # Floor plan takes the spare height, the toolbar sits under it at its natural size
        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.addWidget(self.floorplan, stretch=1)
        left.addWidget(self.toolbar)

        self.dock = TabDock()
        self.dock.set_fixed_tab_width(DOCK_WIDTH)

        layout = QHBoxLayout()
        layout.setContentsMargins(3, 3, 3, 3)
        layout.addLayout(left, stretch=1)
        layout.addWidget(self.dock)
        self.setLayout(layout)
