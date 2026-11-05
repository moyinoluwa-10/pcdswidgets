"""
PVAlarmCircle: a status light that summarizes the alarm state of many PVs.

This is a stand-in for typhos' TyphosAlarmCircle that takes PV addresses instead of an ophyd device,
with the same levels, ordering, and colors.
"""

import enum
from functools import partial

from pydm.widgets.channel import PyDMChannel
from pydm.widgets.drawing import PyDMDrawingCircle
from qtpy import QtCore
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
    AlarmLevel.NO_ALARM: "rgba(0,255,0,255)",  # green
    AlarmLevel.MINOR: "rgba(255,255,0,255)",  # yellow
    AlarmLevel.MAJOR: "rgba(255,0,0,255)",  # red
    AlarmLevel.INVALID: "rgba(255,0,255,255)",  # magenta
    AlarmLevel.DISCONNECTED: "rgba(255,255,255,255)",  # white
}


class PVAlarmCircle(PyDMDrawingCircle):
    """
    A circle that shows the worst alarm state across many PVs.

    Disconnected PVs count as the worst state.
    """

    alarm_changed = QtCore.Signal(int)

    def __init__(self, parent: QWidget | None = None, channels: list[str] | None = None):
        super().__init__(parent)
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

    def alarm_tooltip(self, max_lines: int = 12) -> str:
        """Every PV not in NO_ALARM with its level, worst first (like the typhos tooltip); "" if all are fine."""
        bad = sorted(
            ((self.alarm_for(addr), addr) for addr in self._pv_channels if self.alarm_for(addr) != AlarmLevel.NO_ALARM),
            key=lambda item: -item[0],
        )
        if not bad:
            return ""
        lines = [f"{addr.split('://', 1)[-1]}: {level.name}" for level, addr in bad[:max_lines]]
        if len(bad) > max_lines:
            lines.append(f"... and {len(bad) - max_lines} more")
        return f"{len(bad)} of {len(self._pv_channels)} PVs not OK:\n" + "\n".join(lines)
