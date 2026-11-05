"""
A happi-free, ophyd-free version of pcdswidgets' IndicatorGrid.

The pcdswidgets IndicatorGrid (ported from LUCID) loads devices from happi,
instantiates them with ophyd, summarizes them with a TyphosAlarmCircle, and
opens TyphosDeviceDisplay screens. This module keeps all of the grid, menu, and
TabDock behavior by subclassing, and swaps out only the device-specific parts:

- devices come from ``las_devices.load_devices`` (plain JSON/YAML)
- the indicator is ``PVAlarmCircle``, a PyDM drawing that watches a list of PVs
  and colors itself exactly like TyphosAlarmCircle does
- clicking opens the pydm screen named in ``config/device_types.yaml``
"""

import enum
import logging
import os
from functools import partial

from las_devices import (
    DeviceInfo,
    DeviceType,
    find_device_type,
    group_devices,
    load_device_types,
    load_devices,
)
from pydm.display import ScreenTarget, load_file
from pydm.utilities import is_qt_designer
from pydm.utilities.stylesheet import merge_widget_stylesheet
from pydm.widgets.channel import PyDMChannel
from pydm.widgets.drawing import PyDMDrawingCircle
from qtpy import QtCore, QtWidgets
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QLabel, QVBoxLayout, QWidget

from pcdswidgets.common.dock.indicator_grid import IndicatorCell, IndicatorGrid, IndicatorGroup

try:
    from qtpy.QtCore import Property  # type: ignore
except ImportError:
    from qtpy.QtCore import pyqtProperty as Property  # type: ignore

logger = logging.getLogger(__name__)


class AlarmLevel(enum.IntEnum):
    """Same levels and ordering as typhos.alarm.AlarmLevel."""

    NO_ALARM = 0
    MINOR = 1
    MAJOR = 2
    INVALID = 3
    DISCONNECTED = 4


# Same colors as typhos.alarm.indicator_stylesheet
ALARM_COLORS = {
    AlarmLevel.NO_ALARM: "rgba(0,255,0,255)",
    AlarmLevel.MINOR: "rgba(255,255,0,255)",
    AlarmLevel.MAJOR: "rgba(255,0,0,255)",
    AlarmLevel.INVALID: "rgba(255,0,255,255)",
    AlarmLevel.DISCONNECTED: "rgba(255,255,255,255)",
}


class PVAlarmCircle(PyDMDrawingCircle):
    """
    A circle that shows the worst alarm state across many PVs.

    This is a stand-in for TyphosAlarmCircle that takes a list of channel
    addresses instead of an ophyd device. Disconnected PVs count as the worst state.
    """

    alarm_changed = QtCore.Signal(int)

    def __init__(self, parent: QWidget | None = None, channels: list[str] | None = None, title: str = ""):
        super().__init__(parent)
        self._title = title
        self._pv_channels: dict[str, PyDMChannel] = {}
        self._connected: dict[str, bool] = {}
        self._severity: dict[str, int] = {}
        self.alarm_summary = None
        self.alarm_changed.connect(self.set_alarm_color)
        self.set_alarm_color(AlarmLevel.DISCONNECTED)
        if channels:
            self.set_channels(channels)

    def set_channels(self, addresses: list[str]):
        """Replace the watched PVs."""
        for channel in self._pv_channels.values():
            channel.disconnect()
        self._pv_channels.clear()
        self._connected.clear()
        self._severity.clear()
        for address in dict.fromkeys(addresses):
            self._connected[address] = False
            self._severity[address] = AlarmLevel.INVALID
            channel = PyDMChannel(
                address=address,
                connection_slot=partial(self.update_connection, addr=address),
                severity_slot=partial(self.update_severity, addr=address),
            )
            self._pv_channels[address] = channel
            if not is_qt_designer():
                channel.connect()
        self.update_current_alarm()

    def channels(self):
        """Used by PyDM's middle-click "copy PV names" behavior."""
        return list(self._pv_channels.values())

    def update_connection(self, connected: bool, addr: str):
        self._connected[addr] = connected
        self.update_current_alarm()

    def update_severity(self, severity: int, addr: str):
        self._severity[addr] = severity
        self.update_current_alarm()

    def alarm_for(self, addr: str) -> AlarmLevel:
        if not self._connected.get(addr, False):
            return AlarmLevel.DISCONNECTED
        return AlarmLevel(self._severity.get(addr, AlarmLevel.INVALID))

    def update_current_alarm(self):
        if not self._pv_channels:
            new_alarm = AlarmLevel.INVALID
        else:
            new_alarm = max(self.alarm_for(addr) for addr in self._pv_channels)
        if new_alarm != self.alarm_summary:
            self.alarm_summary = new_alarm
            self.alarm_changed.emit(int(new_alarm))

    def set_alarm_color(self, alarm_level: int):
        color = ALARM_COLORS[AlarmLevel(alarm_level)]
        self.setStyleSheet(
            f"{type(self).__name__} {{border: none; background: transparent; qproperty-brush: {color};}}"
        )

    def alarm_tooltip(self) -> str:
        """Device name, then every PV that is not in NO_ALARM, like the typhos tooltip."""
        lines = [f"Device {self._title}"] if self._title else []
        bad = [
            f"{addr.split('://', 1)[-1]}: {self.alarm_for(addr).name}"
            for addr in self._pv_channels
            if self.alarm_for(addr) != AlarmLevel.NO_ALARM
        ]
        if bad:
            lines.append("-" * 2 * len(lines[-1]) if lines else "--")
            lines.extend(bad)
        return os.linesep.join(lines)

    def event(self, event):
        if event.type() == QtCore.QEvent.ToolTip:
            QtWidgets.QToolTip.showText(event.globalPos(), self.alarm_tooltip(), self)
            return True
        return super().event(event)


def fallback_display(device: DeviceInfo, reason: str) -> QWidget:
    """A placeholder for devices that do not have a screen yet."""
    widget = QWidget()
    widget.setWindowTitle(device.name)
    layout = QVBoxLayout()
    label = QLabel(
        f"<b>{device.name}</b><br>"
        f"class: {device.device_class}<br>"
        f"prefix: {device.prefix or '(none)'}<br>"
        f"location: {device.location_group} / {device.functional_group}<br><br>"
        f"{reason}"
    )
    label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    label.setWordWrap(True)
    layout.addWidget(label)
    layout.addStretch()
    widget.setLayout(layout)
    return widget


class DeviceScreenCache:
    """Builds and caches the pydm screen for each device, like display_for_device does for typhos."""

    def __init__(self, types: dict[str, DeviceType]):
        self.types = types
        self._cache: dict[str, QWidget] = {}

    def display_for_device(self, device: DeviceInfo) -> QWidget:
        try:
            return self._cache[device.name]
        except KeyError:
            ...
        dtype = find_device_type(device, self.types)
        if dtype is None:
            display = fallback_display(device, "No screen is configured for this device class yet.")
        else:
            path = dtype.screen_path()
            if not os.path.isfile(path):
                display = fallback_display(device, f"Screen file not found:<br>{path}")
            else:
                logger.debug("Creating display for %s from %s", device.name, path)
                display = load_file(path, macros=dtype.macros_for(device), target=ScreenTarget.DIALOG)
                display.hide()
                merge_widget_stylesheet(widget=display)
        display.setWindowTitle(device.name)
        self._cache[device.name] = display
        return display


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
        indicator = PVAlarmCircle(channels=channels, title=device.name)
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
