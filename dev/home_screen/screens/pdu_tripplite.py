"""
TrippLite PDU screen (pdu_snmp IOC, TrippLitePdu_N.db): the PyDM version of pduScreens/TrippLite_24.edl.

Same content as the EDM screen (common/pdu_snmp R3.3.6), grouped the same way:

- header: PDU type, prefix, IOC screen (EDM's ioc_soft.edl) and IOC heartbeat
- Power Distribution Unit Info: name and location (editable, autosaved), status, model
- PDU Details: number of inputs, outputs, outlets, groups, phases, circuits, breakers, heatsinks
- Input Details: frequency, voltage, voltage min / max
- Output Details: frequency, voltage, active power, current, current min / max
- Global Control: All On, All Off, Reboot
- Outlet Status & Control: per outlet its ID, name (editable), status, control state, command and ramp option

Every power command (global and per outlet) asks for confirmation first. The EDM screen's per-outlet
command menu is On / Off / Cycle buttons here, with the outlet's current command shown next to them.

Macros:
    PRE     PDU PV prefix, e.g. LAS:LHN:PWR:07
    IOC     IOC PV prefix, for the heartbeat and IOC screen (default: IOC:{PRE})
    TITLE   heading text, e.g. the toolbar button's name (optional)
    N_CHAN  number of outlets (default 24)
"""

from pydm import Display
from pydm.widgets import PyDMEnumComboBox, PyDMLabel, PyDMLineEdit, PyDMPushButton, PyDMShellCommand
from qtpy.QtCore import Qt
from qtpy.QtGui import QFont
from qtpy.QtWidgets import QGridLayout, QGroupBox, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout

# The IOC screen the EDM header links to (iocAdmin's ioc_soft.edl)
IOC_SCREEN = "/reg/g/pcds/epics/iocAdmin/R3.1.16-1.3.2/iocScreens/ioc_soft.edl"

# setPduOutletCommand states
TURN_OFF = 1
TURN_ON = 2
CYCLE = 3
# setPduControlPdu{On,Off,Reboot} states: N/A, True, False
PDU_TRUE = 1

# Button colours by what they do: (background, hover, text, disabled background, disabled text)
BUTTON_COLORS = {
    "on": ("#2e9e4f", "#36b85c", "white", "#a8d5b5", "#eef7f1"),
    "off": ("#c0392b", "#d9483a", "white", "#e3aaa4", "#f8ecea"),
    "cycle": ("#f1c40f", "#f5d33f", "black", "#f6e3a1", "#9a8c5c"),
}


def scaled(name: str, pv: str, factor: float) -> str:
    """A calc:// channel for the SNMP values reported in 0.1 or 0.01 units (as the EDM screen's CALC)."""
    return f"calc://{name}?A=ca://{pv}&expr=A*{factor}"


def bold(text: str, size: int = 0) -> QLabel:
    label = QLabel(text)
    font = QFont()
    font.setBold(True)
    if size:
        font.setPointSize(size)
    label.setFont(font)
    return label


def color_button(button: PyDMPushButton, kind: str) -> PyDMPushButton:
    """Green for on, red for off, yellow for cycle / reboot; faded when disabled (no write access or disconnected)."""
    bg, hover, fg, disabled_bg, disabled_fg = BUTTON_COLORS[kind]
    button.setStyleSheet(
        f"PyDMPushButton {{ background-color: {bg}; color: {fg}; font-weight: 500;"
        f" border: 1px solid rgba(0, 0, 0, 90); border-radius: 3px; padding: 2px 2px; }}"
        f"PyDMPushButton:hover {{ background-color: {hover}; }}"
        f"PyDMPushButton:pressed {{ border: 2px solid rgba(0, 0, 0, 150); }}"
        f"PyDMPushButton:disabled {{ background-color: {disabled_bg}; color: {disabled_fg}; }}"
    )
    return button


def value_label(channel: str, width: int, tooltip: str = "", alarm: bool = False) -> PyDMLabel:
    """
    A readback of ``width`` px. Its size doesn't follow its text: while disconnected a PyDMLabel shows its
    whole channel address, which would otherwise stretch every column far past the dock's width.
    """
    label = PyDMLabel(init_channel=channel)
    label.setToolTip(tooltip or channel.split("://", 1)[-1])
    label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    label.setMinimumWidth(width)
    if alarm:
        label.alarmSensitiveContent = True
    return label


def text_field(channel: str, width: int) -> PyDMLineEdit:
    """An editable text PV that can shrink to ``width`` px and takes any spare width."""
    field = PyDMLineEdit(init_channel=channel)
    field.setToolTip(channel.split("://", 1)[-1])
    field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    field.setMinimumWidth(width)
    return field


class TrippLitePdu(Display):
    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros)
        macros = macros or {}
        self.pre = macros["PRE"]
        self.ioc = macros.get("IOC") or f"IOC:{self.pre}"
        self.n_chan = int(macros.get("N_CHAN", 24))
        self.setWindowTitle(macros.get("TITLE") or self.pre)
        self.setup_ui(macros.get("TITLE", ""))

    def ui_filename(self):
        return None

    def setup_ui(self, title: str):
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.addLayout(self.header(title))
        # PDU info with the global controls beside it, then the three detail panels: fits the dock's width
        top = QHBoxLayout()
        top.addWidget(self.info_box(), stretch=1)
        top.addWidget(self.global_box())
        layout.addLayout(top)
        details = QHBoxLayout()
        for box in (self.pdu_details_box(), self.input_box(), self.output_box()):
            details.addWidget(box)
        layout.addLayout(details)
        layout.addWidget(self.outlets_box())
        layout.addStretch()

    # Sections, in the EDM screen's order

    def header(self, title: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(bold(f"TRIPPLITE {self.n_chan}-PORT PDU", 12))
        # The prefix, as on the EDM screen; the title (e.g. the rack's toolbar button) is the window / tab title
        prefix = bold(self.pre, 12)
        prefix.setTextInteractionFlags(Qt.TextSelectableByMouse)
        if title:
            prefix.setToolTip(title)
        row.addSpacing(24)
        row.addWidget(prefix)
        row.addStretch()
        ioc = PyDMShellCommand()
        ioc.setText("IOC")
        ioc.setToolTip(f"{self.ioc}: IOC status screen (EDM)")
        ioc.commands = [f'edm -x -eolc -m "ioc={self.ioc}" {IOC_SCREEN}']
        ioc.showIcon = False
        row.addWidget(ioc)
        heartbeat = value_label(f"ca://{self.ioc}:HEARTBEAT", 60, f"{self.ioc}:HEARTBEAT", alarm=True)
        heartbeat.alarmSensitiveBorder = True
        # Fixed, not Ignored: with a zero size hint the row's stretch would leave it no room
        heartbeat.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        heartbeat.setFixedWidth(60)
        row.addWidget(heartbeat)
        return row

    def info_box(self) -> QGroupBox:
        box = QGroupBox("Power Distribution Unit Info")
        grid = QGridLayout()
        box.setLayout(grid)
        pre = self.pre
        grid.addWidget(QLabel("Name"), 0, 0)
        grid.addWidget(text_field(f"ca://{pre}:setDeviceName", 160), 0, 1)
        grid.addWidget(QLabel("Status"), 0, 2)
        grid.addWidget(value_label(f"ca://{pre}:getDeviceStatus", 110, alarm=True), 0, 3)
        grid.addWidget(QLabel("Location"), 1, 0)
        grid.addWidget(text_field(f"ca://{pre}:setDeviceLocation", 160), 1, 1)
        grid.addWidget(QLabel("Model"), 1, 2)
        grid.addWidget(value_label(f"ca://{pre}:getDeviceModel", 110), 1, 3)
        # Name / location fields and the status / model readbacks share the spare width
        grid.setColumnStretch(1, 3)
        grid.setColumnStretch(3, 2)
        return box

    def pdu_details_box(self) -> QGroupBox:
        box = QGroupBox("PDU Details")
        grid = QGridLayout()
        box.setLayout(grid)
        items = (
            ("Inputs", "NumInputs", "Phases", "NumPhases"),
            ("Outputs", "NumOutputs", "Circuits", "NumCircuits"),
            ("Outlets", "NumOutlets", "Breakers", "NumBreakers"),
            ("Groups", "NumOutletGroups", "Heatsinks", "NumHeatsinks"),
        )
        for row, (left, left_pv, right, right_pv) in enumerate(items):
            grid.addWidget(QLabel(left), row, 0)
            grid.addWidget(value_label(f"ca://{self.pre}:getPduIdent{left_pv}", 28), row, 1)
            grid.addWidget(QLabel(right), row, 2)
            grid.addWidget(value_label(f"ca://{self.pre}:getPduIdent{right_pv}", 28), row, 3)
        return box

    def measurements_box(self, title: str, rows: tuple[tuple[str, str, float, str], ...]) -> QGroupBox:
        box = QGroupBox(title)
        grid = QGridLayout()
        box.setLayout(grid)
        tag = self.pre.replace(":", "_")
        for row, (label, pv, factor, units) in enumerate(rows):
            grid.addWidget(QLabel(label), row, 0)
            value = value_label(scaled(f"{tag}_{pv}", f"{self.pre}:{pv}", factor), 48, f"{self.pre}:{pv} x {factor}")
            value.precisionFromPV = False
            value.precision = 1
            grid.addWidget(value, row, 1)
            grid.addWidget(QLabel(units), row, 2)
        return box

    def input_box(self) -> QGroupBox:
        return self.measurements_box(
            "Input Details",
            (
                ("Frequency", "getPduInputPhaseFrequency", 0.1, "Hz"),
                ("Voltage", "getPduInputPhaseVoltage", 0.1, "V"),
                ("Voltage (Min)", "getPduInputPhaseVoltageMin", 0.1, "V"),
                ("Voltage (Max)", "getPduInputPhaseVoltageMax", 0.1, "V"),
            ),
        )

    def output_box(self) -> QGroupBox:
        return self.measurements_box(
            "Output Details",
            (
                ("Frequency", "getPduOutputFrequency", 0.1, "Hz"),
                ("Voltage", "getPduOutputVoltage", 0.1, "V"),
                ("Active Power", "getPduOutputActivePower", 0.1, "W"),
                ("Current", "getPduOutputCurrent", 0.01, "A"),
                ("Current (Min)", "getPduOutputCurrentMin", 0.01, "A"),
                ("Current (Max)", "getPduOutputCurrentMax", 0.01, "A"),
            ),
        )

    def global_box(self) -> QGroupBox:
        box = QGroupBox("Global Control")
        column = QVBoxLayout()
        column.setSpacing(2)
        box.setLayout(column)
        for text, pv, verb, kind in (
            ("All On", "setPduControlPduOn", "Turn ON every outlet of", "on"),
            ("All Off", "setPduControlPduOff", "Turn OFF every outlet of", "off"),
            ("Reboot", "setPduControlPduReboot", "Reboot", "cycle"),
        ):
            button = PyDMPushButton(label=text, pressValue=PDU_TRUE, init_channel=f"ca://{self.pre}:{pv}")
            color_button(button, kind)
            button.showConfirmDialog = True
            button.confirmMessage = f"{verb} {self.pre}?"
            button.setToolTip(f"{self.pre}:{pv}")
            button.setMaximumWidth(80)
            column.addWidget(button)
        column.addStretch()
        return box

    def outlets_box(self) -> QGroupBox:
        # "&&": a single "&" in a group box title is a keyboard shortcut marker
        box = QGroupBox("Outlet Status && Control")
        grid = QGridLayout()
        grid.setVerticalSpacing(2)
        box.setLayout(grid)
        headers = ("ID", "Name", "Status", "Controllable", "Command", "", "", "", "Ramp Option")
        for col, text in enumerate(headers):
            grid.addWidget(bold(text), 0, col)
        for n in range(1, self.n_chan + 1):
            outlet = f"{self.pre}:Outlet:{n}"
            grid.addWidget(value_label(f"ca://{outlet}:getPduOutletIndex", 24), n, 0)
            grid.addWidget(text_field(f"ca://{outlet}:setPduOutletName", 96), n, 1)
            grid.addWidget(value_label(f"ca://{outlet}:getPduOutletState", 56, alarm=True), n, 2)
            grid.addWidget(value_label(f"ca://{outlet}:getPduOutletControllable", 44), n, 3)
            grid.addWidget(value_label(f"ca://{outlet}:getPduOutletCommand", 64, alarm=True), n, 4)
            commands = (
                ("On", TURN_ON, "Turn ON", "on"),
                ("Off", TURN_OFF, "Turn OFF", "off"),
                ("Cycle", CYCLE, "Power cycle", "cycle"),
            )
            for col, (text, value, verb, kind) in enumerate(commands, start=5):
                button = PyDMPushButton(label=text, pressValue=value, init_channel=f"ca://{outlet}:setPduOutletCommand")
                color_button(button, kind)
                button.showConfirmDialog = True
                button.confirmMessage = f"{verb} outlet {n} of {self.pre}?"
                button.setFixedWidth(54)
                grid.addWidget(button, n, col)
            ramp = PyDMEnumComboBox(init_channel=f"ca://{outlet}:setPduOutletRampAction")
            # A fixed minimum, not one in characters: its width then doesn't grow with the font
            ramp.setSizeAdjustPolicy(PyDMEnumComboBox.AdjustToMinimumContentsLengthWithIcon)
            ramp.setMinimumContentsLength(1)
            ramp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            ramp.setMinimumWidth(150)
            ramp.setToolTip(f"{outlet}:setPduOutletRampAction (now: {outlet}:getPduOutletRampAction)")
            grid.addWidget(ramp, n, 8)
        grid.setColumnStretch(1, 1)
        return box
