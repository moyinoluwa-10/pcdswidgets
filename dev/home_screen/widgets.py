"""
The floor plan's clickable widgets: ``AreaButton`` (a station, bay, area or rack) and ``IconButton`` (with its
status dot), the menus they show (groups as sub-menus with "Open All", screens with the TabDock options,
commands marked ↗), and the icons, by the names floorplan.yaml uses.
"""

import functools
import logging
from pathlib import Path

from alarm import PVAlarmCircle
from openers import Opener
from pydm.utilities import IconFont
from qtpy.QtCore import QEvent, QPoint, QRect, QRectF, QSize, Qt
from qtpy.QtGui import QBrush, QColor, QIcon, QMouseEvent, QPainter, QPen
from qtpy.QtWidgets import QMenu, QPushButton, QSizePolicy, QToolButton, QToolTip, QWidget

import pcdswidgets
from pcdswidgets.common.dock.tab_dock import TabDock

logger = logging.getLogger(__name__)

# Icons

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


# Menus


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
            if opener.icon:
                action.setIcon(make_icon(opener.icon))
            action.setToolTip(opener.tooltip)
            action.triggered.connect(lambda _=False, o=opener: o.run())
        else:
            menu.addAction(opener.title).setEnabled(False)
    menu.setToolTipsVisible(True)


def add_group_menu(menu: QMenu, opener: Opener):
    """A sub-menu for a group, with "Open All" at the top when there are several screens."""
    sub = ClickableSubmenuMenu(opener.title, menu)
    if opener.icon:
        sub.setIcon(make_icon(opener.icon))
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
    if opener.icon:
        sub.setIcon(make_icon(opener.icon))
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


# Buttons


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
            target.run()
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
    """A drawn area (a station, a bay, the BTS, a rack): colored box with its label centered or at the top."""

    def __init__(
        self,
        name: str,
        openers: list[Opener],
        tooltip: str = "",
        color: str = "#ffffff",
        border: str = "#595959",
        inactive: str | None = None,
        label_size: float = 0.04,
        label_top: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName(name.replace(" ", "_"))
        self.openers = openers
        self.menu_title = name
        self.label = name
        self.badge: QIcon | None = None
        # Racks with nothing to open are greyed out; bays and areas always keep their color
        greyed = bool(inactive) and not openers
        self.color = QColor(inactive if greyed else color)
        self.border = QColor(border)
        self.text_color = QColor(90, 90, 90) if greyed else QColor(0, 0, 0)
        # label height as a fraction of the hall height, so text scales with the drawing
        self.label_size = label_size
        # Stations put their label at the top, so their icons can use the rest of the area
        self.label_top = label_top
        self.hall_height = 600
        self.setCursor(Qt.PointingHandCursor if openers else Qt.ArrowCursor)
        self.setToolTip(tooltip or name)
        self.setFocusPolicy(Qt.NoFocus)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        painter.fillRect(rect, self.color)
        hovered = self.openers and self.underMouse()
        if hovered:
            painter.fillRect(rect, PRESSED_FILL if self.isDown() else HOVER_FILL)
        pen = QPen(HOVER_BORDER, 2) if hovered else QPen(self.border, 1)
        painter.setPen(pen)
        # Lines are centered on their coordinates; inset by half the pen so the outline covers whole pixels
        half = pen.widthF() / 2
        painter.drawRect(QRectF(rect).adjusted(half, half, -half, -half))
        font = painter.font()
        font.setPixelSize(max(7, round(self.hall_height * self.label_size)))
        painter.setFont(font)
        painter.setPen(self.text_color)
        if self.label_top:
            painter.drawText(rect.adjusted(0, font.pixelSize() // 3, 0, 0), Qt.AlignHCenter | Qt.AlignTop, self.label)
        else:
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
        self._style_key: tuple[int, bool, int] | None = None
        self.set_scale(1.0)
        names = [leaf.title for leaf in self.all_leaves()]
        self.setToolTip(f"{label}\n" + "\n".join(names[:12]) + ("\n..." if len(names) > 12 else ""))
        self.status = None
        channels = [ch for opener in openers for ch in opener.all_channels()]
        if status and channels:
            self.status = PVAlarmCircle(parent=self, channels=channels)
            self.status.setFixedSize(10, 10)
            self.status.setAttribute(Qt.WA_TransparentForMouseEvents)
            # Black outline so the dot stays visible on the white icon background (e.g. when disconnected)
            self.status.penStyle = Qt.SolidLine
            self.status.penColor = QColor(0, 0, 0)
            self.status.penWidth = 1
        self.adjustSize()

    def all_leaves(self) -> list[Opener]:
        return [leaf for opener in self.openers for leaf in opener.leaves()]

    def event(self, event):
        # The status dot is transparent to the mouse, so its alarm details are shown in the icon's tooltip
        if event.type() == QEvent.ToolTip and self.status is not None:
            alarms = self.status.alarm_tooltip()
            if alarms:
                QToolTip.showText(event.globalPos(), f"{self.toolTip()}\n\n{alarms}", self)
                return True
        return super().event(event)

    def set_scale(self, scale: float):
        """Shrink with the floor plan so icons don't pile up on small windows."""
        size = max(12, min(28, round(self.icon_size * scale)))
        show_label = scale >= self.label_min_scale
        font_pt = max(6, round(8 * min(scale, 1.2)))
        # Restyling re-polishes the widget, so skip it when nothing visible changes (most resize events)
        if self._style_key == (size, show_label, font_pt):
            return
        self._style_key = (size, show_label, font_pt)
        self.setIconSize(QSize(size, size))
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon if show_label else Qt.ToolButtonIconOnly)
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
