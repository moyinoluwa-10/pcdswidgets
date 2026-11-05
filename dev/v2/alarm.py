"""
PVAlarmCircle: a status light that summarizes the alarm state of many PVs.

This is a stand-in for typhos' TyphosAlarmCircle that takes PV addresses instead of an ophyd device,
with the same levels, ordering, and colors.
"""

import enum
import os
from functools import partial

from pydm.utilities import is_qt_designer
from pydm.widgets.channel import PyDMChannel
from pydm.widgets.drawing import PyDMDrawingCircle
from qtpy import QtCore, QtWidgets
from qtpy.QtWidgets import QWidget


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

    Disconnected PVs count as the worst state.
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
