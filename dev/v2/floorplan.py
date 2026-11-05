"""
Floor-plan home screen pieces for v2: a drawing of the laser hall with clickable areas and icons.

This follows the lasdev style (a floor plan with buttons that open screens in a TabDock), but the hall
is drawn by Qt from ``config/floorplan.yaml`` (bays, racks R01-R20, BTS as laid-out colored areas)
instead of being a background image with hand-placed buttons. Devices come from the happi JSON database
read as plain JSON (devices.py), and screens are pydm/pcdswidgets screens (no happi/ophyd/typhos).

Every clickable thing resolves to a list of ``Opener`` objects:

- one dockable opener: left click opens it in the dock (ctrl: new tab, shift: new window),
  right click shows the dock options menu
- one external opener: click runs the command (EDM and other standalone tools)
- anything else: click shows a menu with a sub-menu per opener
"""

import logging
import os
import re
import shlex
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from alarm import PVAlarmCircle
from devices import DeviceInfo, DeviceScreenCache, find_device_type, load_device_types, load_devices
from pydm.display import ScreenTarget, load_file
from pydm.utilities import IconFont
from pydm.utilities.stylesheet import merge_widget_stylesheet
from qtpy.QtCore import QPoint, QRect, QSize, Qt
from qtpy.QtGui import QBrush, QColor, QIcon, QMouseEvent, QPainter, QPen
from qtpy.QtWidgets import QHBoxLayout, QMenu, QPushButton, QSizePolicy, QToolButton, QVBoxLayout, QWidget

import pcdswidgets
from pcdswidgets.common.dock.tab_dock import TabDock

V2_DIR = Path(__file__).resolve().parent

logger = logging.getLogger(__name__)

CONFIG_FILE = V2_DIR / "config" / "floorplan.yaml"
# "Zone 1 TiSaph PSU/Chiller PDU (R07)" -> R07
RACK_IN_NAME = re.compile(r"\((R\d+)\)")
SCREENS_DIR = V2_DIR / "screens"
TOOLBAR_FILE = V2_DIR / "config" / "las_toolbar.yaml"
# Found through the pcdswidgets package on PYTHONPATH, wherever this directory is copied to
SMARACT_ICON = Path(pcdswidgets.__file__).resolve().parent / "icons" / "smaract_tip_tilt_qt_icon.png"

ifont = IconFont()

# icon name in floorplan.yaml -> FontAwesome name, for the ones that are not literal FontAwesome names
FA_ALIASES = {
    "thermometer": "thermometer-half",
    "pdu": "plug",
    "btps": "shield-alt",
    "external": "external-link-alt",
    "tools": "tools",
}


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


@dataclass
class Opener:
    """Something a click can open: a dockable screen, an external command, or a group of openers."""

    title: str
    icon: QIcon | None = None
    build: Callable[[], QWidget] | None = None
    command: list[str] = field(default_factory=list)
    children: list["Opener"] = field(default_factory=list)
    channels: list[str] = field(default_factory=list)
    tooltip: str = ""
    # happi name, for device openers
    device_name: str = ""

    @property
    def dockable(self) -> bool:
        return self.build is not None

    def all_channels(self) -> list[str]:
        channels = list(self.channels)
        for child in self.children:
            channels.extend(child.all_channels())
        return channels

    def leaves(self) -> list["Opener"]:
        if not self.children:
            return [self]
        return [leaf for child in self.children for leaf in child.leaves()]


def run_command(commands: list[str]):
    """Run toolbar-style shell commands detached, like PyDMShellCommand does."""
    for command in commands:
        logger.info("Running %s", command)
        try:
            subprocess.Popen(shlex.split(os.path.expanduser(command)), start_new_session=True)
        except Exception:
            logger.exception("Failed to run %s", command)


class FloorPlanContext:
    """Loads the configs once and turns ``opens`` entries into Openers."""

    def __init__(
        self,
        config_file: str | os.PathLike = CONFIG_FILE,
        toolbar_file: str | os.PathLike = TOOLBAR_FILE,
        device_db: str | os.PathLike | None = None,
        beamline: str = "LAS",
    ):
        with open(config_file) as fd:
            self.config: dict[str, Any] = yaml.safe_load(fd)
        self.config_dir = Path(config_file).resolve().parent
        with open(toolbar_file) as fd:
            self.toolbar: dict[str, Any] = yaml.safe_load(fd) or {}
        self.devices = load_devices(beamline, device_db)
        self.devices_by_name = {dev.name: dev for dev in self.devices}
        self.types = load_device_types()
        self.screens = DeviceScreenCache(self.types)
        self._screen_cache: dict[str, QWidget] = {}
        self.functions: dict[str, dict[str, str]] = self.config.get("functions", {})
        self.shutters: dict[str, dict[str, str]] = self.config.get("shutters", {})

    # Openers for each kind of entry

    def device_opener(self, device: DeviceInfo, title: str = "") -> Opener:
        dtype = find_device_type(device, self.types)
        function = self.functions.get(device.functional_group, {})
        return Opener(
            title=title or device.name,
            icon=make_icon(function.get("icon", "cube")),
            build=lambda: self.screens.display_for_device(device),
            channels=dtype.indicator_channels_for(device) if dtype is not None else [],
            tooltip=f"{device.name}\n{device.device_class}\n{device.prefix}",
            device_name=device.name,
        )

    def devices_matching(self, locations: list[str], functions: list[str] | None = None) -> list[DeviceInfo]:
        return [
            dev
            for dev in self.devices
            if dev.location_group in locations and (functions is None or dev.functional_group in functions)
        ]

    def function_groups(self, devices: list[DeviceInfo]) -> list[Opener]:
        """One sub-menu per functional_group, in the order of the ``functions`` config."""
        order = list(self.functions)
        groups: dict[str, list[DeviceInfo]] = {}
        for dev in devices:
            groups.setdefault(dev.functional_group, []).append(dev)
        openers = []
        for function in sorted(groups, key=lambda f: (order.index(f) if f in order else len(order), f)):
            cfg = self.functions.get(function, {})
            openers.append(
                Opener(
                    title=cfg.get("title", function),
                    icon=make_icon(cfg.get("icon", "cube")),
                    children=[self.device_opener(dev) for dev in sorted(groups[function], key=lambda d: d.name)],
                )
            )
        return openers

    def shutter_opener(self, source: str) -> Opener:
        cfg = self.shutters.get(source, {})
        title = cfg.get("title", source)
        opener = self.screen_opener(
            {"screen": "laser_shutter.ui", "macros": {"LS": source, "TITLE": title}, "title": f"{title} Shutter"},
            icon="shutter",
        )
        opener.channels = [
            f"ca://LTLHN:{source}:LST:OPN_RBV",
            f"ca://LTLHN:{source}:LST:CLS_RBV",
            f"ca://LTLHN:{source}:BTPS:Error_RBV",
        ]
        return opener

    def screen_opener(self, entry: dict[str, Any], icon: str = "window-maximize") -> Opener:
        path = Path(entry["screen"])
        if not path.is_absolute():
            path = SCREENS_DIR / path
        macros = {key: str(val) for key, val in (entry.get("macros") or {}).items()}
        title = entry.get("title") or path.stem
        key = f"{path}|{sorted(macros.items())}"

        def build() -> QWidget:
            if key not in self._screen_cache:
                widget = load_file(str(path), macros=macros, target=ScreenTarget.DIALOG)
                widget.hide()
                merge_widget_stylesheet(widget=widget)
                widget.setWindowTitle(title)
                self._screen_cache[key] = widget
            return self._screen_cache[key]

        return Opener(title=title, icon=make_icon(entry.get("icon", icon)), build=build, tooltip=str(path))

    def toolbar_opener(self, tab: str, button: str) -> Opener:
        try:
            commands = list(self.toolbar[tab]["buttons"][button]["commands"])
        except KeyError:
            logger.error("No toolbar button %r in tab %r", button, tab)
            return Opener(title=f"{button} (missing)", icon=make_icon("exclamation-triangle"))
        return Opener(title=button, icon=make_icon("external"), command=commands, tooltip="Opens in its own window")

    def rack_openers(self, rack: str, cfg: dict[str, Any]) -> list[Opener]:
        """
        What a rack opens: its own ``opens`` list if it has one, otherwise every button in the
        toolbar's rack tab (the "PDUs" tab) whose name ends with the rack in parentheses, e.g. "... (R07)".
        """
        if "opens" in cfg:
            return self.resolve(cfg["opens"])
        tab = self.config.get("rack_toolbar_tab", "PDUs")
        buttons = self.toolbar.get(tab, {}).get("buttons", {})
        return [
            self.toolbar_opener(tab, name)
            for name in buttons
            if (match := RACK_IN_NAME.search(name)) is not None and match.group(1) == rack
        ]

    def resolve(self, entries: list[dict[str, Any]]) -> list[Opener]:
        """Turn an ``opens`` list from the config into Openers."""
        openers = []
        for entry in entries:
            if "device" in entry:
                device = self.devices_by_name.get(entry["device"])
                if device is None:
                    logger.error("Device %s is not an active %s device", entry["device"], "LAS")
                    continue
                openers.append(self.device_opener(device, entry.get("title", "")))
            elif "devices" in entry:
                query = entry["devices"]
                devices = self.devices_matching(query.get("location", []), query.get("function"))
                openers.extend(self.function_groups(devices))
            elif "shutter" in entry:
                openers.append(self.shutter_opener(entry["shutter"]))
            elif "screen" in entry:
                openers.append(self.screen_opener(entry))
            elif "toolbar" in entry:
                openers.append(self.toolbar_opener(*entry["toolbar"]))
            else:
                logger.error("Unknown opens entry %s", entry)
        return openers

    def bay_openers(self, bay: str, cfg: dict[str, Any]) -> list[Opener]:
        """Every control in a bay: devices by function, then shutters, then external tools."""
        skip = set(self.config.get("bay_menu_skip_functions", []))
        devices = [
            dev for dev in self.devices_matching(cfg.get("locations", [bay])) if dev.functional_group not in skip
        ]
        openers = self.function_groups(devices)
        shutters = [self.shutter_opener(src) for src, scfg in self.shutters.items() if scfg.get("bay") == bay]
        if shutters:
            openers.append(Opener(title="Shutters", icon=make_icon("shutter"), children=shutters))
        tools = [self.toolbar_opener(*tool) for tool in cfg.get("tools", [])]
        if tools:
            openers.append(Opener(title="Tools", icon=make_icon("tools"), children=tools))
        return openers


class ClickableSubmenuMenu(QMenu):
    """A QMenu where clicking a sub-menu entry runs its default action (opens it in the dock)."""

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore
        if event.button() == Qt.LeftButton:
            action = self.actionAt(event.pos())
            submenu = action.menu() if action is not None else None
            default = submenu.defaultAction() if submenu is not None else None
            if default is not None:
                default.trigger()
                self.close()
                return
        super().mousePressEvent(event)


def fill_menu(menu: QMenu, openers: list[Opener]):
    """Add openers to a menu: groups become sub-menus, screens get the TabDock options."""
    for opener in openers:
        if opener.children:
            add_group_menu(menu, opener)
        elif opener.dockable:
            add_dockable_menu(menu, opener)
        elif opener.command:
            action = menu.addAction(opener.title + " ↗")
            if opener.icon is not None:
                action.setIcon(opener.icon)
            action.setToolTip(opener.tooltip)
            action.triggered.connect(lambda _=False, cmd=opener.command: run_command(cmd))
        else:
            menu.addAction(opener.title).setEnabled(False)
    menu.setToolTipsVisible(True)


def add_group_menu(menu: QMenu, opener: Opener):
    """A sub-menu for a group, with "Open All" at the top when there are several screens."""
    sub = ClickableSubmenuMenu(opener.title, menu)
    if opener.icon is not None:
        sub.setIcon(opener.icon)
    dockable = [leaf for leaf in opener.leaves() if leaf.dockable]
    if len(dockable) > 1 and TabDock.dock_exists():
        many = ClickableSubmenuMenu("Open All", sub)
        TabDock.add_many_to_dock_user_menu(
            widget_list=lambda d=dockable: [leaf.build() for leaf in d],
            title_list=[leaf.title for leaf in dockable],
            menu=many,
        )
        sub.addMenu(many)
        sub.addSeparator()
    fill_menu(sub, opener.children)
    menu.addMenu(sub)


def add_dockable_menu(menu: QMenu, opener: Opener):
    """A sub-menu with the TabDock options for one screen. Clicking the entry itself opens it in the dock."""
    sub = ClickableSubmenuMenu(opener.title, menu)
    if opener.icon is not None:
        sub.setIcon(opener.icon)
    if opener.tooltip:
        sub.setToolTip(opener.tooltip)
    if TabDock.dock_exists():
        TabDock.add_to_dock_user_menu(widget=opener.build, title=opener.title, menu=sub)
    else:
        sub.addAction("Open in New Window").triggered.connect(lambda _=False, o=opener: show_floating(o))
    sub.setDefaultAction(sub.actions()[0])
    menu.addMenu(sub)


def show_floating(opener: Opener):
    """Open a screen as its own window, for when there is no TabDock."""
    widget = opener.build()
    widget.setWindowTitle(opener.title)
    TabDock.show_widget_at_cursor(widget)


class OpenerButtonMixin:
    """Mouse handling shared by the area buttons and the icon buttons."""

    openers: list[Opener]
    menu_title: str = ""

    def single(self) -> Opener | None:
        """The one thing a plain click opens, or None if a click should show a menu."""
        leaves = self.openers[0].leaves() if len(self.openers) == 1 else self.openers
        if len(leaves) == 1 and not leaves[0].children:
            return leaves[0]
        return None

    def build_menu(self) -> QMenu:
        menu = ClickableSubmenuMenu(self)
        if self.menu_title:
            menu.addSection(self.menu_title)
        openers = self.openers
        if len(openers) == 1 and openers[0].children:
            openers = openers[0].children
        fill_menu(menu, openers)
        return menu

    def handle_click(self, button: Qt.MouseButton, global_pos: QPoint):
        if not self.openers:
            return
        target = self.single()
        if target is not None and target.dockable:
            if not TabDock.dock_exists():
                show_floating(target)
            elif button == Qt.RightButton:
                TabDock.add_to_dock_user_menu(widget=target.build, title=target.title, pos=global_pos)
            else:
                TabDock.add_to_dock_user_keybinds(widget=target.build, title=target.title)
        elif target is not None and target.command and button == Qt.LeftButton:
            run_command(target.command)
        else:
            self.build_menu().exec_(global_pos)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # type: ignore
        if event.button() in (Qt.LeftButton, Qt.RightButton) and self.rect().contains(event.pos()):
            self.setDown(False)
            self.handle_click(event.button(), event.globalPos())
            return
        super().mouseReleaseEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore
        if event.button() == Qt.RightButton:
            return
        super().mousePressEvent(event)


HOVER_FILL = QColor(20, 140, 210, 40)
PRESSED_FILL = QColor(20, 140, 210, 90)
HOVER_BORDER = QColor(20, 140, 210, 200)


class AreaButton(OpenerButtonMixin, QPushButton):
    """A drawn area of the hall (a bay, the BTS, a rack): colored box with a centered label."""

    def __init__(
        self,
        name: str,
        openers: list[Opener],
        tooltip: str = "",
        color: str = "#ffffff",
        border: str = "#595959",
        inactive: str | None = None,
        label_size: float = 0.04,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName(name.replace(" ", "_"))
        self.openers = openers
        self.menu_title = name
        self.label = name
        self.badge: QIcon | None = None
        # Racks with nothing to open are greyed out; bays and areas always keep their color
        self.color = QColor(inactive if (inactive and not openers) else color)
        self.border = QColor(border)
        self.text_color = QColor(90, 90, 90) if (inactive and not openers) else QColor(0, 0, 0)
        # label height as a fraction of the hall height, so text scales with the drawing
        self.label_size = label_size
        self.hall_height = 600
        self.setCursor(Qt.PointingHandCursor if openers else Qt.ArrowCursor)
        self.setToolTip(tooltip or name)
        self.setFocusPolicy(Qt.NoFocus)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

    @property
    def inactive(self) -> bool:
        return not self.openers

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)
        painter.fillRect(rect, self.color)
        hovered = self.openers and self.underMouse()
        if hovered:
            painter.fillRect(rect, PRESSED_FILL if self.isDown() else HOVER_FILL)
        painter.setPen(QPen(HOVER_BORDER, 2) if hovered else QPen(self.border, 1))
        painter.drawRect(rect)
        font = painter.font()
        font.setPixelSize(max(7, round(self.hall_height * self.label_size)))
        painter.setFont(font)
        painter.setPen(self.text_color)
        painter.drawText(rect, Qt.AlignCenter, self.label)
        if self.badge is not None:
            size = max(8, min(self.width(), self.height()) // 4)
            self.badge.paint(painter, QRect(self.width() - size - 3, self.height() - size - 3, size, size))


class IconButton(OpenerButtonMixin, QToolButton):
    """A small labeled icon placed on the floor plan, with an optional status dot."""

    icon_size = 22
    # Below this hall scale the label is dropped and only the icon is shown
    label_min_scale = 0.75

    def __init__(
        self, label: str, icon: QIcon, openers: list[Opener], status: bool = True, parent: QWidget | None = None
    ):
        super().__init__(parent)
        self.openers = openers
        self.menu_title = label
        self.setIcon(icon)
        self.setIconSize(QSize(self.icon_size, self.icon_size))
        self.setText(label)
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.set_scale(1.0)
        names = [leaf.title for leaf in self.all_leaves()]
        self.setToolTip(f"{label}\n" + "\n".join(names[:12]) + ("\n..." if len(names) > 12 else ""))
        self.status = None
        channels = [ch for opener in openers for ch in opener.all_channels()]
        if status and channels:
            self.status = PVAlarmCircle(parent=self, channels=channels, title=label)
            self.status.setFixedSize(10, 10)
            self.status.setAttribute(Qt.WA_TransparentForMouseEvents)
            # Black outline so the dot stays visible on the white icon background (e.g. when disconnected)
            self.status.penStyle = Qt.SolidLine
            self.status.penColor = QColor(0, 0, 0)
            self.status.penWidth = 1
        self.adjustSize()

    def all_leaves(self) -> list[Opener]:
        return [leaf for opener in self.openers for leaf in opener.leaves()]

    def set_scale(self, scale: float):
        """Shrink with the floor plan so icons don't pile up on small windows."""
        size = max(12, min(28, round(self.icon_size * scale)))
        self.setIconSize(QSize(size, size))
        show_label = scale >= self.label_min_scale
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon if show_label else Qt.ToolButtonIconOnly)
        font_pt = max(6, round(8 * min(scale, 1.2)))
        self.setStyleSheet(
            "QToolButton { background: rgba(255, 255, 255, 215); border: 1px solid rgb(120, 120, 120);"
            f" border-radius: 4px; font-size: {font_pt}pt; padding: 1px; }}"
            "QToolButton:hover { border: 2px solid rgba(20, 140, 210, 220); }"
        )
        self.ensurePolished()
        self.updateGeometry()

    def sizeHint(self) -> QSize:
        if self.toolButtonStyle() == Qt.ToolButtonIconOnly:
            # The style's hint lags behind stylesheet changes; a square around the icon is what we want anyway
            side = self.iconSize().width() + 14
            return QSize(side, side)
        return super().sizeHint()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.status is not None:
            self.status.move(self.width() - 11, 1)


def rack_names(spec: str) -> list[str]:
    """ "R01-R05" -> ["R01", ..., "R05"]"""
    first, last = (int(part.strip().lstrip("R")) for part in spec.split("-"))
    return [f"R{n:02d}" for n in range(first, last + 1)]


def stretch(percent: float) -> int:
    """QBoxLayout stretch factors are ints; keep two decimals of the configured shares."""
    return max(0, round(percent * 100))


class Hall(QWidget):
    """
    The laser hall drawing, built from the "hall" section of floorplan.yaml.

    A QHBoxLayout of columns, left to right. Each column is a QVBoxLayout whose stretch factors
    place its area(s) vertically, so everything is proportional and there are no coordinates.
    """

    def __init__(self, floor: "FloorPlan", parent: QWidget | None = None):
        super().__init__(parent)
        context = floor.context
        self.cfg = context.config["hall"]
        self.background = QColor(self.cfg.get("background", "#eeeeee"))
        self.border = QColor(self.cfg.get("border", "#595959"))
        self.areas: dict[str, AreaButton] = {}
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        for column in self.cfg["columns"]:
            if "gap" in column:
                row.addStretch(stretch(column["gap"]))
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
        area = AreaButton(name, openers, tooltip, color=color, border=self.cfg.get("border", "#595959"), **kwargs)
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
                    tooltip = f'{rack}: no toolbar button named "... ({rack})" (or add opens: in config/floorplan.yaml)'
                area = self.make_area(
                    rack,
                    openers,
                    tooltip,
                    group["color"],
                    inactive=self.cfg.get("inactive", "#b7b7b7"),
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
    The drawn laser hall with icons on top.

    The hall keeps its aspect ratio (hall.aspect in floorplan.yaml) and is centered in the widget.
    Icons are positioned at a percentage of their area and resized with the hall.
    """

    # Size of the original drawing; the hall is laid out at any size, this is only the preferred one
    reference_height = 659

    def __init__(self, context: FloorPlanContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.context = context
        self.aspect = float(context.config["hall"].get("aspect", 2.0))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.hall = Hall(self, parent=self)
        # Racks are generated, so list areas in a stable order for callers: (button, kind)
        self.areas: list[tuple[AreaButton, str]] = [(area, name) for name, area in self.hall.areas.items()]
        self.icons: list[tuple[IconButton, tuple[str, float, float]]] = []
        self._scale = 1.0
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
        self._scale = height / self.reference_height
        for area in self.hall.areas.values():
            area.hall_height = height
            area.update()
        for button, (area_name, x_frac, y_frac) in self.icons:
            area = self.hall.areas[area_name]
            origin = area.mapTo(self, QPoint(0, 0))
            center = QPoint(origin.x() + round(area.width() * x_frac), origin.y() + round(area.height() * y_frac))
            button.set_scale(self._scale)
            size = button.sizeHint()
            button.setGeometry(
                center.x() - size.width() // 2, center.y() - size.height() // 2, size.width(), size.height()
            )
            button.raise_()
