"""
A happi-free, ophyd-free version of pcdswidgets' IndicatorGrid.

The pcdswidgets IndicatorGrid (ported from LUCID) loads devices from happi,
instantiates them with ophyd, summarizes them with a TyphosAlarmCircle, and
opens TyphosDeviceDisplay screens. This module keeps all of the grid, menu, and
TabDock behavior by subclassing, and swaps out only the device-specific parts:

- devices come from ``devices.load_devices`` (plain JSON/YAML)
- the indicator is ``alarm.PVAlarmCircle``, a PyDM drawing that watches a list of PVs
  and colors itself exactly like TyphosAlarmCircle does
- clicking opens the pydm screen named in ``config/device_types.yaml``
"""

import logging
import os

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
from qtpy import QtCore, QtWidgets
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QWidget

from pcdswidgets.common.dock.indicator_grid import IndicatorCell, IndicatorGrid, IndicatorGroup

try:
    from qtpy.QtCore import Property  # type: ignore
except ImportError:
    from qtpy.QtCore import pyqtProperty as Property  # type: ignore

logger = logging.getLogger(__name__)


class GridAlarmCircle(PVAlarmCircle):
    """A grid cell's status light: its tooltip names the device, then lists the PVs that aren't OK (like typhos)."""

    def __init__(self, parent: QWidget | None = None, channels: list[str] | None = None, title: str = ""):
        self._title = title
        super().__init__(parent, channels=channels)

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
    """Replaces BaseDeviceButton.show_device so it opens pydm screens instead of typhos ones."""

    screens: DeviceScreenCache

    def show_device(self, device: DeviceInfo) -> QWidget:
        return self.screens.display_for_device(device)


class PVIndicatorCell(_PVDeviceButtonMixin, IndicatorCell):
    def __init__(self, *args, screens: DeviceScreenCache, **kwargs):
        self.screens = screens
        super().__init__(*args, **kwargs)

    def add_device(self, device: DeviceInfo):
        dtype = find_device_type(device, self.screens.types)
        channels = dtype.indicator_channels_for(device) if dtype is not None else []
        indicator = GridAlarmCircle(channels=channels, title=device.name)
        indicator.setContextMenuPolicy(Qt.NoContextMenu)
        self.devices.append(device)
        self.add_indicator(indicator)


class PVIndicatorGroup(_PVDeviceButtonMixin, IndicatorGroup):
    def __init__(self, *args, screens: DeviceScreenCache, **kwargs):
        self.screens = screens
        super().__init__(*args, **kwargs)


class LasIndicatorGrid(IndicatorGrid):
    """
    IndicatorGrid that loads from the happi JSON database (or a YAML snapshot) with no happi import.

    Set ``deviceDatabase`` (optional, defaults to the path in $HAPPI_CFG),
    ``deviceTypes`` (optional, defaults to config/device_types.yaml),
    then ``beamline`` to populate the grid.
    """

    _qt_designer_ = {
        "group": "LAS Dev",
        "is_container": False,
    }

    def __init__(self, parent: QWidget | None = None):
        self._database = ""
        self._types_file = ""
        self.devices: list[DeviceInfo] = []
        super().__init__(parent=parent)
        self.screens = DeviceScreenCache(load_device_types())

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
        cell = PVIndicatorCell(screens=self.screens)
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
        group = PVIndicatorGroup(title=group_name, orientation="row" if as_row else "column", screens=self.screens)
        self._groups[group.title] = group
        if as_row:
            (row, column) = (0, self.grid.columnCount())
        else:
            (row, column) = (self.grid.rowCount(), 0)
        self.grid.addWidget(group, row, column, Qt.AlignVCenter)
