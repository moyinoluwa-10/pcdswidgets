"""Menus of Openers: groups as sub-menus (with "Open All"), screens with the TabDock options, commands marked ↗."""

from icons import make_icon
from openers import Opener
from qtpy.QtCore import Qt
from qtpy.QtGui import QMouseEvent
from qtpy.QtWidgets import QMenu

from pcdswidgets.common.dock.tab_dock import TabDock


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
