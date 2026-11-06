"""
Qmini spectrometer screen from the IOC's own widgets (common/qmini R3.1.1 qminiScreens).

This is ``QminiSpectrometer.embedded.py`` from that release (the screen LUCID opens), loaded from
there: the spectrum + fit plot with auto-ranging, recolour, show/hide fit, single exposure and
save spectrum, plus "Parameters" / "Fit Settings" buttons that open the release's qmini_subwindows
as floating windows.

Macros:
    prefix  spectrometer PV prefix, e.g. LM1K4:EJX_DP1_SP1 (lower case, as the release's .ui uses)
    NAME    window title (default: prefix)
"""

import importlib.util
import sys

from pydm import Display
from qtpy.QtWidgets import QVBoxLayout

QMINI_SCREENS = "/cds/group/pcds/epics/ioc/common/qmini/R3.1.1/qminiScreens"
MODULE = "qmini_spectrometer_embedded"


def embedded_class():
    """The release's QminiSpectrometerEmbeddedUI (its file name has a dot, so import it by path)."""
    if MODULE not in sys.modules:
        spec = importlib.util.spec_from_file_location(MODULE, f"{QMINI_SCREENS}/QminiSpectrometer.embedded.py")
        module = importlib.util.module_from_spec(spec)
        # Registered before running: pydm finds the .ui next to sys.modules[cls.__module__].__file__
        sys.modules[MODULE] = module
        spec.loader.exec_module(module)
    return sys.modules[MODULE].QminiSpectrometerEmbeddedUI


class QminiScreen(Display):
    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros)
        macros = macros or {}
        self.setWindowTitle(macros.get("NAME") or macros.get("prefix", "Qmini"))

        self.qmini = embedded_class()(parent=self, macros=macros)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.qmini)
        self.setLayout(layout)

    def ui_filename(self):
        return None
