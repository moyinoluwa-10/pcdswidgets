"""
A happi-free, ophyd-free version of pcdswidgets' IndicatorGrid.

The pcdswidgets IndicatorGrid (ported from LUCID) loads devices from happi,
instantiates them with ophyd, summarizes them with a TyphosAlarmCircle, and
opens TyphosDeviceDisplay screens. This module keeps all of the grid, menu, and
TabDock behavior by subclassing, and swaps out only the device-specific parts:

- devices come from ``devices.load_devices`` (plain JSON/YAML)
- the indicator is ``alarm.PVAlarmCircle``, a PyDM drawing that watches a list of PVs
  and colors itself exactly like TyphosAlarmCircle does
- clicking opens the pydm screen named in ``config/device_types.yaml``, except for the devices in
  ``config/grid.yaml`` (the BTPS), which run a LAS toolbar button instead, as in dev/las
"""

import logging
import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml
from alarm import PVAlarmCircle
from devices import (
    DeviceInfo,
    DeviceScreenCache,
    find_device_type,
    group_devices,
    load_device_types,
    load_devices,
)
from pydm.utilities import is_qt_designer
from pydm.utilities.iconfont import IconFont
from qtpy import QtCore, QtWidgets
from qtpy.QtCore import QEvent, Qt
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QLabel, QWidget

from pcdswidgets.common.dock.indicator_grid import IndicatorCell, IndicatorGrid, IndicatorGroup
from pcdswidgets.common.dock.tab_dock import TabDock

try:
    from qtpy.QtCore import Property  # type: ignore
except ImportError:
    from qtpy.QtCore import pyqtProperty as Property  # type: ignore

logger = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent
GRID_CONFIG = APP_DIR / "config" / "grid.yaml"
TOOLBAR_FILE = APP_DIR / "config" / "las_toolbar.yaml"


@dataclass
class ToolbarTool:
    """A toolbar button a grid device runs instead of opening a screen (e.g. the BTPS Overview)."""

    title: str
    commands: list[str]
    icon: str = "external-link-alt"


def run_command(commands: list[str]):
    """Run toolbar-style shell commands detached, like PyDMShellCommand does."""
    for command in commands:
        logger.info("Running %s", command)
        try:
            subprocess.Popen(shlex.split(os.path.expanduser(command)), start_new_session=True)
        except Exception:
            logger.exception("Failed to run %s", command)


def load_toolbar_tools(
    toolbar_file: str | os.PathLike = TOOLBAR_FILE, config_file: str | os.PathLike = GRID_CONFIG
) -> dict[str, ToolbarTool]:
    """happi name -> the toolbar button it runs, from config/grid.yaml and the toolbar yaml."""
    with open(config_file) as fd:
        entries = (yaml.safe_load(fd) or {}).get("toolbar_devices") or {}
    with open(toolbar_file) as fd:
        toolbar = yaml.safe_load(fd) or {}
    tools = {}
    for name, cfg in entries.items():
        tab, button = cfg["toolbar"]
        try:
            commands = list(toolbar[tab]["buttons"][button]["commands"])
        except KeyError:
            logger.error("No toolbar button %r in tab %r for %s", button, tab, name)
            commands = []
        tools[name] = ToolbarTool(title=button, commands=commands, icon=cfg.get("icon", "external-link-alt"))
    return tools


class GridAlarmCircle(PVAlarmCircle):
    """A grid cell's status light: its tooltip names the device, then lists the PVs that aren't OK (like typhos)."""

    def __init__(self, parent: QWidget | None = None, channels: list[str] | None = None, title: str = ""):
        self._title = title
        super().__init__(parent, channels=channels)
        # Thin black outline, as on dev/las's status dots
        self.penStyle = Qt.SolidLine
        self.penColor = QColor(0, 0, 0)
        self.penWidth = 1.5

    def cell_tooltip(self) -> str:
        lines = [f"Device {self._title}"] if self._title else []
        bad = self.alarm_tooltip()
        if bad:
            lines.append("-" * 2 * len(lines[-1]) if lines else "--")
            lines.append(bad)
        return os.linesep.join(lines)

    def event(self, event):
        if event.type() == QtCore.QEvent.ToolTip:
            QtWidgets.QToolTip.showText(event.globalPos(), self.cell_tooltip(), self)
            return True
        return super().event(event)


class _PVDeviceButtonMixin:
    """
    Replaces BaseDeviceButton's typhos parts: devices open pydm screens, and toolbar devices
    (``tools``, e.g. the BTPS) run their toolbar button instead of going to the dock.
    """

    screens: DeviceScreenCache
    tools: dict[str, ToolbarTool]

    def show_device(self, device: DeviceInfo) -> QWidget:
        return self.screens.display_for_device(device)

    def dockable_devices(self) -> list[DeviceInfo]:
        return [device for device in self.devices if device.name not in self.tools]

    def show_all(self) -> list[QWidget]:
        return [self.show_device(device) for device in self.dockable_devices()]

    def get_all_titles(self) -> list[str]:
        return [device.name for device in self.dockable_devices()]

    def _menu_shown(self):
        """BaseDeviceButton._menu_shown, with toolbar devices as plain external entries."""
        existing = [action.text() for action in self.device_menu.actions()]
        if self._OPEN_ALL not in existing and len(self.dockable_devices()) > 1:
            sub_menu = self.device_menu.addMenu(self._OPEN_ALL)
            TabDock.add_many_to_dock_user_menu(widget_list=self.show_all, title_list=self.get_all_titles, menu=sub_menu)
            self.device_menu.addSeparator()
        for device in self.devices:
            tool = self.tools.get(device.name)
            if tool is None:
                if device.name not in existing:
                    self._add_to_menu(widget_func=self._show_device_wrapper(device), text=device.name)
            elif f"{tool.title} \u2197" not in existing:
                action = self.device_menu.addAction(IconFont().icon(tool.icon), f"{tool.title} \u2197")
                action.setToolTip(f"{device.name}: opens in its own window")
                action.triggered.connect(lambda _=False, commands=tool.commands: run_command(commands))

    def eventFilter(self, obj, event):  # type: ignore
        """A button whose only device is a toolbar device: left click runs it, right click shows the menu."""
        if event.type() == QEvent.MouseButtonPress and len(self.devices) == 1 and self.devices[0].name in self.tools:
            if event.button() == Qt.LeftButton:
                run_command(self.tools[self.devices[0].name].commands)
                return True
            if event.button() == Qt.RightButton:
                self.device_menu.exec_(event.globalPos())
                return True
        return super().eventFilter(obj, event)


class PVIndicatorCell(_PVDeviceButtonMixin, IndicatorCell):
    def __init__(self, *args, screens: DeviceScreenCache, tools: dict[str, ToolbarTool], **kwargs):
        self.screens = screens
        self.tools = tools
        super().__init__(*args, **kwargs)

    def add_device(self, device: DeviceInfo):
        tool = self.tools.get(device.name)
        if tool is not None:
            # No status dot, as in dev/las: the icon of what a click opens
            indicator = QLabel()
            indicator.setPixmap(IconFont().icon(tool.icon).pixmap(self.icon_size, self.icon_size))
            indicator.setToolTip(f"{device.name}\nRuns the toolbar's {tool.title!r} (opens in its own window)")
        else:
            dtype = find_device_type(device, self.screens.types)
            channels = dtype.indicator_channels_for(device) if dtype is not None else []
            indicator = GridAlarmCircle(channels=channels, title=device.name)
        indicator.setContextMenuPolicy(Qt.NoContextMenu)
        self.devices.append(device)
        self.add_indicator(indicator)


class PVIndicatorGroup(_PVDeviceButtonMixin, IndicatorGroup):
    def __init__(self, *args, screens: DeviceScreenCache, tools: dict[str, ToolbarTool], **kwargs):
        self.screens = screens
        self.tools = tools
        super().__init__(*args, **kwargs)


class LasIndicatorGrid(IndicatorGrid):
    """
    IndicatorGrid that loads from the happi JSON database (or a YAML snapshot) with no happi import.

    Set ``deviceDatabase`` (optional, defaults to the path in $HAPPI_CFG),
    ``deviceTypes`` (optional, defaults to config/device_types.yaml),
    ``toolbarFile`` (optional, defaults to config/las_toolbar.yaml; where config/grid.yaml's toolbar devices
    find their command), then ``beamline`` to populate the grid.
    """

    _qt_designer_ = {
        "group": "LAS Dev",
        "is_container": False,
    }

    def __init__(self, parent: QWidget | None = None):
        self._database = ""
        self._types_file = ""
        self._toolbar_file = str(TOOLBAR_FILE)
        self.devices: list[DeviceInfo] = []
        super().__init__(parent=parent)
        self.screens = DeviceScreenCache(load_device_types())
        self.tools = load_toolbar_tools(self._toolbar_file)

    def get_database(self) -> str:
        return self._database

    def set_database(self, path: str):
        self._database = path

    deviceDatabase = Property("QString", get_database, set_database)

    def get_types_file(self) -> str:
        return self._types_file

    def set_types_file(self, path: str):
        self._types_file = path
        if path:
            self.screens = DeviceScreenCache(load_device_types(path))

    deviceTypes = Property("QString", get_types_file, set_types_file)

    def get_toolbar_file(self) -> str:
        return self._toolbar_file

    def set_toolbar_file(self, path: str):
        self._toolbar_file = path or str(TOOLBAR_FILE)
        self.tools = load_toolbar_tools(self._toolbar_file)

    toolbarFile = Property("QString", get_toolbar_file, set_toolbar_file)

    def set_beamline(self, beamline: str):
        """Set the beamline and, outside of designer, load its devices."""
        self._beamline = beamline
        if beamline and not is_qt_designer():
            self.load_devices(beamline)

    def get_beamline(self) -> str:
        return self._beamline

    beamline = Property("QString", get_beamline, set_beamline)

    def load_devices(self, beamline: str):
        """Read the device list and fill the grid. This is fast enough to run on the GUI thread."""
        self.devices = load_devices(beamline, self._database or None)
        if not self.devices:
            raise ValueError(f"Could not find entries for beamline {beamline}")
        self.add_from_dict(group_devices(self.devices))

    def load_happi(self, beamline: str):
        """Overridden so nothing in this class can reach happi or ophyd."""
        self.load_devices(beamline)

    # The two methods below are copies of IndicatorGrid's, using our cell and group types.

    def add_devices(self, devices: list[DeviceInfo], system: str, stand: str):
        cell = PVIndicatorCell(screens=self.screens, tools=self.tools)
        for device in devices:
            cell.add_device(device)
        coords = []
        for i, group_name in enumerate((system, stand)):
            if group_name not in self._groups:
                self._add_group(group_name, bool(i))
            group = self._groups[group_name]
            idx = self.grid.indexOf(group)
            coords.append(self.grid.getItemPosition(idx)[i])
            if cell:
                group.add_cell(cell)
        if cell:
            self.grid.addWidget(cell, coords[0], coords[1], Qt.AlignTop)

    def _add_group(self, group_name: str, as_row: bool):
        group = PVIndicatorGroup(
            title=group_name, orientation="row" if as_row else "column", screens=self.screens, tools=self.tools
        )
        self._groups[group.title] = group
        if as_row:
            (row, column) = (0, self.grid.columnCount())
        else:
            (row, column) = (self.grid.rowCount(), 0)
        self.grid.addWidget(group, row, column, Qt.AlignVCenter)
