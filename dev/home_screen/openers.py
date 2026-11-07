"""What a click can open (``Opener``), how external commands run, and the scroll area docked screens go in."""

import logging
import os
import shlex
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field

from qtpy.QtWidgets import QFrame, QScrollArea, QWidget

logger = logging.getLogger(__name__)


@dataclass
class Opener:
    """Something a click can open: a dockable screen, an external command, or a group of openers."""

    title: str
    # Icon name (make_icon): kept as a name so building openers from the config needs no Qt application
    icon: str = ""
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

    def run(self):
        """Run this opener's external command."""
        run_command(self.command)


def run_command(commands: list[str]):
    """Run toolbar-style shell commands detached, like PyDMShellCommand does."""
    for command in commands:
        logger.info("Running %s", command)
        try:
            subprocess.Popen(shlex.split(os.path.expanduser(command)), start_new_session=True)
        except Exception:
            logger.exception("Failed to run %s", command)


class DockScreen(QScrollArea):
    """
    A screen as it goes in the dock: in a scroll area, so a screen taller (or wider) than the dock scrolls
    and still fills the dock when there's room. Without it, the screen's minimum height reaches the window
    through the dock's layout and the whole window grows to fit (past the bottom of a short monitor).
    """

    def __init__(self, display: QWidget, parent: QWidget | None = None):
        super().__init__(parent)
        self.display = display
        self.setFrameShape(QFrame.NoFrame)
        self.setWidgetResizable(True)
        self.setWidget(display)
        # load_screen leaves the display hidden; as our child it now shows with us
        display.show()
        self.setWindowTitle(display.windowTitle())
        self.hide()
