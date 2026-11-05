"""
Thorlabs Elliptec stage screen (thorlabs-ell IOC): one screen for every stage type.

elliptec.ui has every section; this drops the ones the stage's IOC records don't have
(see the IOC's st.cmd: which dbs each ELL type loads).

Macros:
    MOTOR  stage PV base, {prefix}:M{channel}, e.g. LM2K2:EJX:ELL:2:M1
    NAME   title
    STAGE  continuous (ELL14/17/18/20 rotation and linear stages, the default), ell6 (2-position
           slider) or ell9 (4-position slider)
"""

from pydm import Display
from qtpy.QtWidgets import QWidget

# Widgets in elliptec.ui that each stage type doesn't have
REMOVE = {
    # Numeric position with units; no position names
    "continuous": ["move_choice", "names_box"],
    # Enum position, 2 names; no jog step, home, clean or stop
    "ell6": [
        "move_value",
        "jog_step_label",
        "jog_step",
        "jog_step_set",
        "home",
        "clean",
        "stop",
        "name2",
        "name2_label",
        "name3",
        "name3_label",
    ],
    # Enum position, 4 names, jog step and home; no clean or stop
    "ell9": ["move_value", "clean", "stop"],
}


class ElliptecScreen(Display):
    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros, ui_filename="elliptec.ui")
        macros = macros or {}
        self.stage = macros.get("STAGE", "continuous")
        self.setWindowTitle(macros.get("NAME") or macros.get("MOTOR", "Elliptec"))
        for name in REMOVE[self.stage]:
            widget = self.findChild(QWidget, name)
            # Deferred delete (disconnects its PV): freeing it now can crash pydm's rules thread
            widget.hide()
            widget.deleteLater()
