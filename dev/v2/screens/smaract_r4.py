"""
SmarAct MCS2 screen built from the IOC's own widgets (common/smaract R4.0.0 motorScreens).

This is ``smaract_expert_screen.py`` from that release without the collapsible "More controls"
section: the expert panel (smaract_expert.ui) on top and the advanced controls tabs
(smaract_advanced_controls.ui) always shown under it. The PicoScale tab is left out.

The widgets are used through the release's generated classes rather than by loading the .ui files,
because loading smaract_advanced_controls.ui on its own hits a circular import in that package
(its form imports widgets.extended_widgets, which imports back into generated).

Macros:
    MOTOR            motor PV, e.g. LAS:BTS:MCS2:01:m1
    SMARACT_SCREENS  motorScreens directory of the IOC release (default: R4.0.0, which the LAS BTS IOC uses)
"""

import os
import sys

from pydm import Display
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QVBoxLayout

SMARACT_SCREENS = "/cds/group/pcds/epics/ioc/common/smaract/R4.0.0/motorScreens"


class SmarActR4(Display):
    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros)
        macros = macros or {}
        screens_dir = macros.get("SMARACT_SCREENS", SMARACT_SCREENS)
        if screens_dir not in sys.path:
            sys.path.insert(0, screens_dir)
        # Importing generated first is the import order that avoids the package's circular import
        from smaract_widgets.generated import SmaractAdvancedControlsBase, SmaractExpertBase

        motor = macros["MOTOR"]
        self.setWindowTitle(macros.get("NAME") or motor)

        self.expert = SmaractExpertBase()
        self.expert.set_macro("motor", motor)
        self.advanced = SmaractAdvancedControlsBase()
        self.advanced.set_macro("motor", motor)

        # Both panels at their natural size, top-left, with the spare space below
        layout = QVBoxLayout()
        layout.addWidget(self.expert, alignment=Qt.AlignLeft)
        layout.addWidget(self.advanced, alignment=Qt.AlignLeft)
        layout.addStretch()
        self.setLayout(layout)

    def ui_filename(self):
        return None

    def loaded_file(self) -> str:
        # Same as smaract_expert_screen.py: give pydm a real file for relative lookups in child widgets
        return os.path.abspath(__file__)
