"""
LAS home screen built from pcdswidgets: a LUCID look-alike with no happi, ophyd, pcdsdevices, or typhos.

Layout matches lucid.main_window.LucidMainWindow:

    +---------------------------+----------------+
    | indicator grid            |                |
    |                           |   TabDock      |
    |   (spacer)                |   (850 px)     |
    | YAML toolbar tabs         |                |
    +---------------------------+----------------+

Run it with ``dev/v1/las_home.sh``, or directly::

    pydm --hide-nav-bar --hide-menu-bar --hide-status-bar dev/v1/las_home.py

Macros (all optional):
    BEAMLINE      happi beamline to load (default: LAS)
    TOOLBAR       toolbar yaml (default: dev/v1/config/las_toolbar.yaml)
    DEVICE_DB     happi JSON database or YAML snapshot (default: from $LAS_DEVICE_DB / $HAPPI_CFG)
    DEVICE_TYPES  device class config (default: dev/v1/config/device_types.yaml)
"""

import logging
import os
import sys
from pathlib import Path

DEV_DIR = Path(__file__).resolve().parent
if str(DEV_DIR) not in sys.path:
    sys.path.insert(0, str(DEV_DIR))

from las_grid import LasIndicatorGrid  # noqa: E402
from pydm import Display  # noqa: E402
from qtpy.QtCore import QSize, Qt, QTimer  # noqa: E402
from qtpy.QtGui import QGuiApplication, QResizeEvent  # noqa: E402
from qtpy.QtWidgets import (  # noqa: E402
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSpacerItem,
    QTabWidget,
    QVBoxLayout,
)

from pcdswidgets.common.dock.tab_dock import TabDock  # noqa: E402
from pcdswidgets.common.toolbar.yaml_toolbar import YamlToolbar  # noqa: E402

logger = logging.getLogger(__name__)

DEFAULT_TOOLBAR = DEV_DIR / "config" / "las_toolbar.yaml"
DOCK_WIDTH = 850

# Let toolbar/BTPS shell buttons find dev/v1/bin/las-open-device with the same python we run in.
os.environ["PATH"] = f"{DEV_DIR / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}"
os.environ.setdefault("LAS_DEV_PYTHON", sys.executable)


class LasHome(Display):
    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros)
        macros = macros or {}
        self.beamline = macros.get("BEAMLINE", "LAS")
        self.toolbar_file = macros.get("TOOLBAR", str(DEFAULT_TOOLBAR))
        self.setup_ui(device_db=macros.get("DEVICE_DB", ""), device_types=macros.get("DEVICE_TYPES", ""))
        QTimer.singleShot(0, self.finalize_window_settings)

    def ui_filename(self):
        return None

    def setup_ui(self, device_db: str, device_types: str):
        self.setWindowTitle(f"{self.beamline} Home (pcdswidgets dev)")

        self.grid = LasIndicatorGrid()
        if device_types:
            self.grid.deviceTypes = device_types
        if device_db:
            self.grid.deviceDatabase = device_db
        self.grid.beamline = self.beamline

        self.dock = TabDock()
        self.dock.set_fixed_tab_width(DOCK_WIDTH)
        self.dock.grid_changed.connect(self.fixed_grid_selected)

        # Shown in place of the dock when the window is too narrow, same as LUCID
        self.dummy_tabs = QTabWidget()
        self.dock_vis_label = QLabel()
        self.dock_vis_label.setAlignment(Qt.AlignCenter)
        self.dummy_tabs.addTab(self.dock_vis_label, "")
        self.dummy_tabs.setEnabled(False)
        self.dummy_tabs.hide()

        self.grid_hlayout = QHBoxLayout()
        self.grid_hlayout.setContentsMargins(0, 0, 0, 0)
        self.grid_hlayout.addWidget(self.grid)
        self.grid_hlayout.addWidget(self.dummy_tabs)
        self.grid_hlayout.setAlignment(self.grid, Qt.AlignLeft)

        self.left_vlayout = QVBoxLayout()
        self.left_vlayout.setContentsMargins(0, 0, 0, 0)
        self.left_vlayout.addLayout(self.grid_hlayout)
        self.left_vlayout.addItem(QSpacerItem(10, 20, QSizePolicy.Minimum, QSizePolicy.MinimumExpanding))
        self.toolbar = YamlToolbar()
        self.toolbar.filename = self.toolbar_file
        self.left_vlayout.addWidget(self.toolbar)
        if self.toolbar.default_dock_button is not None:
            default_docked = self.toolbar.default_dock_button.build_widget()
            TabDock.add_to_dock(title=default_docked.windowTitle(), widget=default_docked)

        self.outer_hlayout = QHBoxLayout()
        self.outer_hlayout.setContentsMargins(3, 3, 3, 3)
        self.outer_hlayout.setSpacing(0)
        self.outer_hlayout.addLayout(self.left_vlayout)
        self.outer_hlayout.addWidget(self.dock)
        self.setLayout(self.outer_hlayout)

        self.width_threshold = 2200
        self.min_placeholder_space = 300
        self.original_min_width = 100

    def resizeEvent(self, event: QResizeEvent) -> None:  # type: ignore
        """Show the dock when there is room for it, otherwise show the placeholder, like LUCID."""
        new_width = event.size().width()
        if new_width < self.width_threshold:
            self.dock.hide()
            if new_width > self.min_placeholder_space:
                self.dock_vis_label.setText(
                    f"Small window mode: dock hidden\n(needs to be {self.width_threshold - new_width}px wider)"
                )
                self.dummy_tabs.show()
            else:
                self.dummy_tabs.hide()
        else:
            self.dock.show()
            self.dummy_tabs.hide()
        return super().resizeEvent(event)

    def finalize_window_settings(self):
        """Size the window from the loaded grid and toolbar, like LucidMainWindow.finalize_window_settings."""
        grid_hint = self.grid.sizeHint()
        tabs_hint = self.toolbar.sizeHint()
        self.width_threshold = grid_hint.width() + DOCK_WIDTH - 20
        minw = max(grid_hint.width(), tabs_hint.width()) + 10
        minh = grid_hint.height() + tabs_hint.height()
        self.setMinimumSize(minw, minh)
        self.min_placeholder_space = grid_hint.width() + 210
        self.original_min_width = minw

        screens = QGuiApplication.screens()
        if screens:
            leftmost = min(screen.geometry().left() for screen in screens)
            rightmost = max(screen.geometry().right() for screen in screens)
            total_width = rightmost - leftmost
        else:
            total_width = self.get_best_width()
        window = self.window()
        size = window.sizeHint()
        width = min(total_width, self.get_best_width() + (window.width() - self.width()))
        window.resize(max(width, minw), max(size.height(), minh))

    def get_best_width(self) -> int:
        return self.grid.sizeHint().width() + DOCK_WIDTH + 8

    def fixed_grid_selected(self):
        """Once the user picks an NxN dock size, adjust our sizing."""
        good_width = self.get_best_width()
        if self.dock.dock_cols == 1:
            self.setMinimumWidth(self.original_min_width)
        else:
            self.setMinimumWidth(good_width)
        window = self.window()
        if window.width() > good_width + 200:
            window.resize(good_width, window.height())

    def sizeHint(self) -> QSize:
        size = super().sizeHint()
        size.setWidth(self.get_best_width())
        return size
