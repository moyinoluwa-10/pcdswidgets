"""
A floor-plan home screen (the lasdev style: floor plan + TabDock), for any location: its floorplan.yaml says
what to draw, which happi beamline to load and which toolbar to show.

Floor plan on top, the location's toolbar under it, dock on the right:

    +-----------------------------------+----------------+
    |   location drawing with clickable |                |
    |   areas (stations, bays, racks)   |   TabDock      |
    |   and icons                       |                |
    |-----------------------------------|                |
    |   toolbar tabs                    |                |
    +-----------------------------------+----------------+

A location is a ``<location>_home.py`` next to its ``floorplan.yaml`` (see ``example/``)::

    intelclass = location_home(Path(__file__).parent / "floorplan.yaml")

Run it with ``pydm --hide-nav-bar --hide-menu-bar --hide-status-bar <location>_home.py``.

Macros:
    FLOORPLAN   the location's floorplan.yaml (set by location_home)
    TOOLBAR     toolbar yaml (default: the floorplan.yaml's ``toolbar``)
    DEVICE_DB   happi JSON database or YAML snapshot (default: $HOME_DEVICE_DB, then happi's from $HAPPI_CFG)
"""

import os
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
if str(PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_DIR))

from context import FloorPlanContext  # noqa: E402
from floorplan import FloorPlan  # noqa: E402
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


class FloorPlanHome(Display):
    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros)
        macros = macros or {}
        if not macros.get("FLOORPLAN"):
            raise RuntimeError("No FLOORPLAN macro: open a <location>_home.py, not home.py")
        self.context = FloorPlanContext(
            config_file=macros["FLOORPLAN"],
            toolbar_file=macros.get("TOOLBAR") or None,
            device_db=macros.get("DEVICE_DB") or None,
        )
        self.setup_ui(toolbar_file=str(self.context.toolbar_file))

    def ui_filename(self):
        return None

    def setup_ui(self, toolbar_file: str):
        self.setWindowTitle(f"{self.context.title} (pcdswidgets dev)")

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


def location_home(floorplan: str | os.PathLike) -> type[FloorPlanHome]:
    """The home screen class for one location's floorplan.yaml (a <location>_home.py's ``intelclass``)."""

    class LocationHome(FloorPlanHome):
        def __init__(self, parent=None, args=None, macros=None):
            super().__init__(parent=parent, args=args, macros={"FLOORPLAN": str(floorplan), **(macros or {})})

    return LocationHome
