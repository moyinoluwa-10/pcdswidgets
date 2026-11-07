"""
SmarAct tip/tilt mirror screen: pcdswidgets' MotorTipTiltDouble (d-pad, step size, positions).

Axes as in pcdsdevices' SmarActTipTilt screen: tip is left/right, tilt is up/down.

Macros:
    TIP    tip axis PV, e.g. LM2K4:COM_MP2_MR4_TIP1 (happi prefix + tip_pv)
    TILT   tilt axis PV
    NAME   title (default: TIP)
    STYLE  Smaract (open-loop step fields, the default) or MotorRecord (closed-loop motor records)
"""

from pathlib import Path

from pydm import Display
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QLabel, QVBoxLayout

import pcdswidgets
from pcdswidgets.motion.common.motor_style import MotorStyle
from pcdswidgets.motion.common.motor_tip_tilt_double import MotorTipTiltDouble

# The widget's related-display paths are relative to the pcdswidgets checkout (pcdswidgets/ui/...)
PCDSWIDGETS_ROOT = Path(pcdswidgets.__file__).resolve().parent.parent


class TipTiltScreen(Display):
    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros)
        macros = macros or {}
        name = macros.get("NAME") or macros["TIP"]
        self.setWindowTitle(name)

        self.tip_tilt = MotorTipTiltDouble()
        self.tip_tilt.motor_style = MotorStyle[macros.get("STYLE", "Smaract")]
        self.tip_tilt.set_motors(horizontal_motor=macros["TIP"], vertical_motor=macros["TILT"])
        for button in (self.tip_tilt.vertical_expert_screen_smaract, self.tip_tilt.horizontal_expert_screen_smaract):
            button.filenames = [str(PCDSWIDGETS_ROOT / f) for f in button.filenames]

        title = QLabel(name)
        title.setStyleSheet("font-weight: bold")
        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(self.tip_tilt)
        layout.addStretch()
        layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setLayout(layout)

    def ui_filename(self):
        return None
