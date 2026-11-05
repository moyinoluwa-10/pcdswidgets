"""
BTPS screen: the same screen as the LAS toolbar's "BTPS Overview" button, opened in the dock.

That button runs /cds/group/pcds/epics-dev/screens/pydm/las/bts/run_btps.sh, which starts ``btps``
from btms-ui v2.0.1 (btms_ui.launch_btps -> BtpsStackedScreen). This display loads the same .ui
files straight from that release and repeats BtpsStackedScreen's small amount of logic
(LS/LD selector buttons, one stacked page per source/destination pair, View/Edit mode).

It does not import btms_ui.core or btms_ui.util, because those pull in ophyd and pcdsdevices.
Only btms_ui.config.btms_config (standard library only) is used, for the list of valid ports.

The screen is much wider than the 850 px dock (the overview has a column per destination),
so in the dock it sits in a scroll area. Shift+click opens it in its own full-size window.

Macros:
    BTMS_UI   btms-ui source directory (default: the v2.0.1 release that run_btps.sh uses)
"""

import json
import logging
import sys
from functools import partial
from pathlib import Path

from pydm import Display
from pydm.widgets import PyDMEmbeddedDisplay, PyDMEnumComboBox, PyDMLineEdit
from qtpy.QtCore import QRegularExpression
from qtpy.QtWidgets import QPushButton, QScrollArea, QVBoxLayout, QWidget
from qtpy.uic import loadUiType

logger = logging.getLogger(__name__)

BTMS_UI = "/reg/g/pcds/pyps/apps/btms-ui/v2.0.1/src/rhel9-x86_64"

# Same look as btms_ui.ui.btps_stacked_screen.BtpsStackedScreen.configure_button
BUTTON_STYLE = """
QPushButton { background-color: #f0f0f0; border: 1px solid #ababab; padding: 5px; border-radius: 3px; }
QPushButton:hover { background-color: #e0e0e0; }
QPushButton:checked { background-color: #3cda02; color: white; font-weight: bold; border: 1px solid #3dcb0a; }
QPushButton:checked:hover { background-color: #3dcb0a; }
"""


def btps_ui_dir(macros: dict | None = None) -> Path:
    return Path((macros or {}).get("BTMS_UI", BTMS_UI)) / "btms_ui" / "ui" / "btps"


class BtpsStacked(Display):
    """The dock entry point: BtpsStackedWidget in a scroll area."""

    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros)
        self.setWindowTitle("BTPS")
        self.stacked = BtpsStackedWidget(btps_ui_dir(macros))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.stacked)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)
        self.setLayout(layout)

    def ui_filename(self):
        return None


class BtpsStackedWidget(QWidget):
    """btms_ui's BtpsStackedScreen, loaded from the release's .ui files without btms_ui.core/util."""

    def __init__(self, ui_dir: Path, parent: QWidget | None = None):
        super().__init__(parent)
        self.ui_dir = ui_dir
        # Same as btms_ui.core.DesignerDisplay: compile the .ui and set it up on this widget
        form, _ = loadUiType(str(ui_dir / "btps_stacked_screen.ui"))
        self.ui_form = form()
        self.ui_form.setupUi(self)
        for name in dir(self.ui_form):
            if not name.startswith("_") and isinstance(getattr(self.ui_form, name), QWidget):
                setattr(self, name, getattr(self.ui_form, name))
        btms_src = str(ui_dir.parents[2])
        if btms_src not in sys.path:
            sys.path.insert(0, btms_src)
        from btms_ui.config import btms_config

        self.sources = [str(source) for source in btms_config.valid_sources]
        self.destinations = [str(dest) for dest in btms_config.valid_destinations]
        self.current_view = {"source": "LS0", "dest": "LD0"}
        self.stack_index = {"LS0_LD0": 0}

        self.btps_overview_widget.setFilename(str(self.ui_dir / "btps-overview.ui"))
        self.editor_button.toggled.connect(self.toggle_edit_button)
        for source in self.sources:
            for dest in self.destinations:
                self.add_page(source, dest)
        self.update_view()
        self.init_buttons()

    def add_page(self, source: str, dest: str):
        """One embedded btps-source-dest.ui per source/destination pair, loaded when first shown."""
        page = PyDMEmbeddedDisplay(parent=self.stacked_widget)
        macros = {
            "SOURCE": f"LTLHN:{dest}:{source}:",
            "DEST": f"LTLHN:{dest}:",
            "SHUTTER": f"LTLHN:{source}:BTPS:",
            "RANGE_SCREEN": str(self.ui_dir / "btps-range-config.ui"),
        }
        page.setMacros(json.dumps(macros))
        page.loadWhenShown = True
        page.disconnectWhenHidden = False
        page.setFilename(str(self.ui_dir / "btps-source-dest.ui"))
        page.setObjectName(f"{source}_{dest}_widget")
        self.stack_index[f"{source}_{dest}"] = self.stacked_widget.addWidget(page)

    def init_buttons(self):
        """Show only the selector buttons for ports that exist, keeping the layout spacing."""
        for button in self.findChildren(QPushButton, QRegularExpression("LS|LD")):
            button.setCheckable(True)
            button.setStyleSheet(BUTTON_STYLE)
            button.toggled.connect(partial(self.toggle_button, button))
            button.setEnabled(False)
            policy = button.sizePolicy()
            policy.setRetainSizeWhenHidden(True)
            button.setSizePolicy(policy)
            button.hide()
        for name in self.sources + self.destinations:
            button = getattr(self, f"{name}_button")
            button.setEnabled(True)
            button.show()

    def toggle_button(self, button: QPushButton, checked: bool):
        """Selecting a source or destination unselects the others of the same kind."""
        name = button.objectName().split("_", maxsplit=1)[0]
        if checked:
            kind, names = ("source", self.sources) if name.startswith("LS") else ("dest", self.destinations)
            self.current_view[kind] = name
            for other in names:
                other_button = getattr(self, f"{other}_button")
                if other_button is not button and other_button.isChecked():
                    self.uncheck_quietly(other_button)
        else:
            self.current_view = {"source": "LS0", "dest": "LD0"}
        self.update_view()

    @staticmethod
    def uncheck_quietly(button: QPushButton):
        button.blockSignals(True)
        button.setChecked(False)
        button.blockSignals(False)

    def update_view(self):
        key = f"{self.current_view['source']}_{self.current_view['dest']}"
        self.stacked_widget.setCurrentIndex(self.stack_index.get(key, 0))
        self.toggle_edit_widgets(self.editor_button.isChecked())

    def toggle_edit_button(self, checked: bool):
        self.editor_button.setText("Edit Mode" if checked else "View Mode")
        self.toggle_edit_widgets(checked)

    def toggle_edit_widgets(self, enabled: bool):
        """Show and enable the range setpoint widgets only in Edit Mode."""
        page = self.stacked_widget.currentWidget()
        for widget in page.findChildren((PyDMLineEdit, PyDMEnumComboBox), QRegularExpression("Setpoint")):
            widget.setEnabled(enabled)
            widget.setVisible(enabled)
