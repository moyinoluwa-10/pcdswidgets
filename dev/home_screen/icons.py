"""Icons for the floor plan, by the names floorplan.yaml uses: the glyphs pcdswidgets uses for the same screens."""

import functools
import logging
from pathlib import Path

from pydm.utilities import IconFont
from qtpy.QtGui import QBrush, QColor, QIcon

import pcdswidgets

logger = logging.getLogger(__name__)

# Found through the pcdswidgets package on PYTHONPATH, wherever this directory is copied to
SMARACT_ICON = Path(pcdswidgets.__file__).resolve().parent / "icons" / "smaract_tip_tilt_qt_icon.png"

ifont = IconFont()

# icon name in floorplan.yaml -> FontAwesome name, for the ones that are not literal FontAwesome names
FA_ALIASES = {
    "thermometer": "thermometer-half",
    "pdu": "plug",
    "btps": "shield-alt",
    "spectrometer": "wave-square",
    "elliptec": "sync-alt",
    "power-meter": "tachometer-alt",
    "wavefront": "bullseye",
    "external": "external-link-alt",
}


@functools.lru_cache(maxsize=None)
def make_icon(name: str) -> QIcon:
    """Icons that match the screens they open: the same glyphs pcdswidgets uses for those widgets."""
    if name == "smaract" and SMARACT_ICON.is_file():
        return QIcon(str(SMARACT_ICON))
    if name == "shutter":
        return shutter_icon()
    return ifont.icon(FA_ALIASES.get(name, name))


_SHUTTER_ICON = None


def shutter_icon() -> QIcon:
    """Render pcdswidgets' FastShutterSymbolIcon into a QIcon."""
    global _SHUTTER_ICON
    if _SHUTTER_ICON is None:
        try:
            from pcdswidgets.symbols.valves import FastShutterSymbolIcon

            symbol = FastShutterSymbolIcon()
            symbol.brush = QBrush(QColor(90, 90, 90))
            symbol.resize(32, 32)
            _SHUTTER_ICON = QIcon(symbol.grab())
            symbol.deleteLater()
        except Exception:
            logger.debug("Falling back to a FontAwesome shutter icon", exc_info=True)
            _SHUTTER_ICON = ifont.icon("door-closed")
    return _SHUTTER_ICON
