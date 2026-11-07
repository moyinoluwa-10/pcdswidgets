"""
The floor-plan widget: a drawing of a location (the laser hall, a MODS table, ...) with clickable areas and
icons, built from that location's ``floorplan.yaml``.

The drawing (``Hall``) is laid out by Qt from the floorplan.yaml "hall" section: columns of stations, bays,
areas and racks. ``FloorPlan`` keeps its aspect ratio and places the icons on it. What each area and icon opens
comes from ``FloorPlanContext`` (context.py) as a list of ``Opener`` objects (openers.py). A click on an area
or icon (widgets.py) does this with them:

- one dockable opener: left click opens it in the dock (ctrl: new tab, shift: new window),
  right click shows the dock options menu
- one external opener: click runs the command (EDM and other standalone tools)
- anything else: click shows a menu with a sub-menu per opener

The rest of the package: devices.py (happi entries and device screens), alarm.py (status dots).
"""

import logging
from typing import Any

from qtpy.QtCore import QPoint, QSize
from qtpy.QtGui import QColor, QPainter, QPen
from qtpy.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from .context import FloorPlanContext
from .openers import Opener
from .widgets import AreaButton, IconButton, make_icon

logger = logging.getLogger(__name__)


def rack_names(spec: str) -> list[str]:
    """ "R01-R05" -> ["R01", ..., "R05"]"""
    first, last = (int(part.strip().lstrip("R")) for part in spec.split("-"))
    return [f"R{n:02d}" for n in range(first, last + 1)]


def stretch(percent: float) -> int:
    """QBoxLayout stretch factors are ints; keep two decimals of the configured shares."""
    return max(0, round(percent * 100))


class Hall(QWidget):
    """
    The location drawing, built from the "hall" section of floorplan.yaml.

    A QHBoxLayout of columns, left to right. Each column is a QVBoxLayout whose stretch factors
    place its area(s) vertically, so everything is proportional and there are no coordinates.
    """

    def __init__(self, context: "FloorPlanContext", parent: QWidget | None = None):
        super().__init__(parent)
        self.cfg = context.config["hall"]
        self.background = QColor(self.cfg.get("background", "#eeeeee"))
        self.border = QColor(self.cfg.get("border", "#595959"))
        # Fill for stations and racks with nothing to open
        self.inactive = self.cfg.get("inactive", "#d7d7d7")
        self.areas: dict[str, AreaButton] = {}
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        for column in self.cfg["columns"]:
            if "gap" in column:
                row.addStretch(stretch(column["gap"]))
            elif "station" in column:
                name = column["station"]
                cfg = context.config.get("stations", {}).get(name, {})
                openers = context.station_openers(name, cfg)
                tooltip = f"{cfg.get('title', name)}: click for all controls in the station"
                area = self.make_area(name, openers, tooltip, column["color"], inactive=self.inactive, label_top=True)
                row.addLayout(self.area_column(area, column), stretch(column["width"]))
            elif "bay" in column:
                bay = column["bay"]
                bay_cfg = context.config.get("bays", {}).get(bay, {})
                openers = context.bay_openers(bay, bay_cfg)
                area = self.make_area(bay, openers, f"{bay}: click for all controls in the bay", column["color"])
                row.addLayout(self.area_column(area, column), stretch(column["width"]))
            elif "area" in column:
                name = column["area"]
                area_cfg = context.config.get("areas", {}).get(name, {})
                openers = context.resolve(area_cfg.get("opens", []))
                area = self.make_area(name, openers, f"{name}: click for options", column["color"])
                row.addLayout(self.area_column(area, column), stretch(column["width"]))
            elif "racks" in column:
                row.addLayout(self.rack_column(column, context), stretch(column["width"]))
            else:
                logger.error("Unknown hall column %s", column)

    def make_area(self, name: str, openers: list[Opener], tooltip: str, color: str, **kwargs) -> AreaButton:
        area = AreaButton(name, openers, tooltip, color=color, border=self.border.name(), **kwargs)
        self.areas[name] = area
        return area

    @staticmethod
    def area_column(area: AreaButton, column: dict[str, Any]) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(0)
        top, height = column["top"], column["height"]
        layout.addStretch(stretch(top))
        layout.addWidget(area, stretch(height))
        layout.addStretch(stretch(100 - top - height))
        return layout

    def rack_column(self, column: dict[str, Any], context: "FloorPlanContext") -> QVBoxLayout:
        """Stacks of racks, e.g. R01-R05 and R06-R10, each group in its own color."""
        layout = QVBoxLayout()
        layout.setSpacing(0)
        groups = column["racks"]
        margin, gap = column.get("top", 5), column.get("group_gap", 4)
        count = sum(len(rack_names(group["range"])) for group in groups)
        rack_height = (100 - 2 * margin - gap * (len(groups) - 1)) / count
        overrides = context.config.get("racks") or {}
        layout.addStretch(stretch(margin))
        for index, group in enumerate(groups):
            if index:
                layout.addStretch(stretch(gap))
            for rack in rack_names(group["range"]):
                openers = context.rack_openers(rack, overrides.get(rack, {}))
                if openers:
                    tooltip = f"{rack}:\n" + "\n".join(opener.title for opener in openers)
                else:
                    tooltip = f'{rack}: no toolbar button named "... ({rack})"'
                area = self.make_area(
                    rack,
                    openers,
                    tooltip,
                    group["color"],
                    inactive=self.inactive,
                    label_size=0.03,
                )
                if openers:
                    area.badge = make_icon("pdu")
                layout.addWidget(area, stretch(rack_height))
        layout.addStretch(stretch(margin))
        return layout

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.rect().adjusted(0, 0, -1, -1)
        painter.fillRect(rect, self.background)
        painter.setPen(QPen(self.border, 1))
        painter.drawRect(rect)


class FloorPlan(QWidget):
    """
    The drawn location with icons on top.

    The hall keeps its aspect ratio (hall.aspect in floorplan.yaml) and is centered in the widget.
    Icons are positioned at a percentage of their area and resized with the hall.
    """

    def __init__(self, context: FloorPlanContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.context = context
        self.aspect = float(context.config["hall"].get("aspect", 2.0))
        # Preferred drawing height (scale 1.0); it is laid out at any size, with half of this as the minimum
        self.reference_height = int(context.config["hall"].get("reference_height", 659))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.hall = Hall(context, parent=self)
        # Racks are generated, so list areas in a stable order for callers: (button, name)
        self.areas: list[tuple[AreaButton, str]] = [(area, name) for name, area in self.hall.areas.items()]
        self.icons: list[tuple[IconButton, tuple[str, float, float]]] = []
        self.build_icons()

    def build_icons(self):
        for icon_cfg in self.context.config.get("icons", []):
            area_name = icon_cfg["in"]
            if area_name not in self.hall.areas:
                logger.error("Icon %s is in unknown area %r", icon_cfg.get("label"), area_name)
                continue
            openers = self.context.resolve(icon_cfg.get("opens", []))
            button = IconButton(
                label=icon_cfg.get("label", ""),
                icon=make_icon(icon_cfg.get("icon", "cube")),
                openers=openers,
                status=icon_cfg.get("status", True),
                parent=self,
            )
            x_pct, y_pct = icon_cfg.get("at", [50, 50])
            self.icons.append((button, (area_name, x_pct / 100, y_pct / 100)))

    def area(self, name: str) -> AreaButton:
        return self.hall.areas[name]

    def sizeHint(self) -> QSize:
        return QSize(round(self.reference_height * self.aspect), self.reference_height)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint() / 2

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return int(width / self.aspect)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        width = min(self.width(), int(self.height() * self.aspect))
        height = int(width / self.aspect)
        self.hall.setGeometry((self.width() - width) // 2, (self.height() - height) // 2, width, height)
        # Lay out the hall now so area geometry is final before placing icons
        self.hall.layout().activate()
        scale = height / self.reference_height
        for area in self.hall.areas.values():
            area.hall_height = height
            area.update()
        for button, (area_name, x_frac, y_frac) in self.icons:
            area = self.hall.areas[area_name]
            origin = area.mapTo(self, QPoint(0, 0))
            center = QPoint(origin.x() + round(area.width() * x_frac), origin.y() + round(area.height() * y_frac))
            button.set_scale(scale)
            size = button.sizeHint()
            button.setGeometry(
                center.x() - size.width() // 2, center.y() - size.height() // 2, size.width(), size.height()
            )
            button.raise_()
