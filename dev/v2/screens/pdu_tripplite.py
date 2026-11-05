"""
TrippLite PDU screen (pdu_snmp IOC, TrippLitePdu_N.db), the PyDM stand-in for TrippLite_24.edl.

Macros:
    PRE     PDU PV prefix, e.g. LAS:LHN:PWR:07
    TITLE   heading text (optional)
    N_CHAN  number of outlets (default 24)

Outlet commands always ask for confirmation. The whole-PDU on/off/reboot controls
from the EDM screen are left out on purpose: use the EDM screen for those.
"""

from pydm import Display
from pydm.widgets import PyDMLabel, PyDMPushButton
from qtpy.QtCore import Qt
from qtpy.QtGui import QFont
from qtpy.QtWidgets import QFormLayout, QGridLayout, QGroupBox, QLabel, QScrollArea, QVBoxLayout, QWidget

# setPduOutletCommand enum values
TURN_OFF = 1
TURN_ON = 2
CYCLE = 3


def scaled(name: str, pv: str, factor: float) -> str:
    """A calc:// channel for the SNMP values reported in 0.1 or 0.01 units."""
    return f"calc://{name}?A=ca://{pv}&expr=A*{factor}"


class TrippLitePdu(Display):
    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros)
        macros = macros or {}
        self.pre = macros["PRE"]
        self.n_chan = int(macros.get("N_CHAN", 24))
        self.setWindowTitle(macros.get("TITLE") or self.pre)
        self.setup_ui(macros.get("TITLE", ""))

    def ui_filename(self):
        return None

    def setup_ui(self, title: str):
        pre = self.pre
        layout = QVBoxLayout()
        self.setLayout(layout)

        heading = QLabel(f"{title}  ({pre})" if title else pre)
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        heading.setFont(font)
        heading.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(heading)

        info = QGroupBox("PDU")
        form = QFormLayout()
        info.setLayout(form)
        for label, pv in (
            ("Name", "getDeviceName"),
            ("Location", "getDeviceLocation"),
            ("Model", "getDeviceModel"),
            ("Status", "getDeviceStatus"),
        ):
            form.addRow(label, PyDMLabel(init_channel=f"ca://{pre}:{pv}"))
        tag = pre.replace(":", "_")
        for label, pv, factor, units in (
            ("Input Voltage", "getPduInputPhaseVoltage", 0.1, "V"),
            ("Input Frequency", "getPduInputPhaseFrequency", 0.1, "Hz"),
            ("Output Current", "getPduOutputCurrent", 0.01, "A"),
            ("Output Power", "getPduOutputActivePower", 1, "W"),
        ):
            value = PyDMLabel(init_channel=scaled(f"{tag}_{pv}", f"{pre}:{pv}", factor))
            value.setToolTip(f"{pre}:{pv} x {factor} {units}")
            row = QWidget()
            row_layout = QGridLayout()
            row_layout.setContentsMargins(0, 0, 0, 0)
            row.setLayout(row_layout)
            row_layout.addWidget(value, 0, 0)
            row_layout.addWidget(QLabel(units), 0, 1)
            form.addRow(label, row)
        layout.addWidget(info)

        outlets = QWidget()
        grid = QGridLayout()
        outlets.setLayout(grid)
        for col, text in enumerate(("#", "Name", "State", "Controllable", "Command", "", "", "")):
            header = QLabel(f"<b>{text}</b>")
            grid.addWidget(header, 0, col)
        for n in range(1, self.n_chan + 1):
            outlet = f"{pre}:Outlet:{n}"
            grid.addWidget(QLabel(str(n)), n, 0)
            grid.addWidget(PyDMLabel(init_channel=f"ca://{outlet}:getPduOutletName"), n, 1)
            state = PyDMLabel(init_channel=f"ca://{outlet}:getPduOutletState")
            state.alarmSensitiveContent = True
            grid.addWidget(state, n, 2)
            grid.addWidget(PyDMLabel(init_channel=f"ca://{outlet}:getPduOutletControllable"), n, 3)
            grid.addWidget(PyDMLabel(init_channel=f"ca://{outlet}:getPduOutletCommand"), n, 4)
            for col, (text, value) in enumerate((("On", TURN_ON), ("Off", TURN_OFF), ("Cycle", CYCLE)), start=5):
                button = PyDMPushButton(label=text, pressValue=value, init_channel=f"ca://{outlet}:setPduOutletCommand")
                button.showConfirmDialog = True
                button.confirmMessage = f"{text} outlet {n} on {pre}?"
                grid.addWidget(button, n, col)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(outlets)
        group = QGroupBox("Outlets")
        group_layout = QVBoxLayout()
        group.setLayout(group_layout)
        group_layout.addWidget(scroll)
        layout.addWidget(group, stretch=1)
