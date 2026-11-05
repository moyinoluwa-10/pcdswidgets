"""
Device list loading and device screens for the LAS home screen, without happi, ophyd, or pcdsdevices.

We only need a handful of metadata fields per device, so we read the happi JSON database as plain JSON
(or a YAML snapshot exported from it, see ``tools/export_happi_devices.py``) and never import happi.

The per-class behavior (which screen to open, which macros to pass, which PVs summarize the
alarm state) lives in ``config/device_types.yaml``.
"""

from __future__ import annotations

import configparser
import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget

logger = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent
CONFIG_DIR = APP_DIR / "config"
SCREENS_DIR = APP_DIR / "screens"
DEFAULT_TYPES_FILE = CONFIG_DIR / "device_types.yaml"
DEFAULT_HAPPI_CFG = "/cds/group/pcds/pyps/apps/hutch-python/device_config/happi.cfg"

LOCATION_KEY = "location_group"
FUNCTION_KEY = "functional_group"
# happi kwargs are templates on the entry's own fields, e.g. tip_pv: '{{ioc_tip_suffix}}'
HAPPI_TEMPLATE = re.compile(r"{{\s*(\w+)\s*}}")


@dataclass(frozen=True)
class DeviceInfo:
    """The subset of a happi entry that the home screen needs."""

    name: str
    device_class: str
    prefix: str = ""
    location_group: str = ""
    functional_group: str = ""
    documentation: str = ""
    # The entry's happi kwargs (filled in, without "name"), e.g. {"tip_pv": "_TIP1"} or {"channel": "1"}
    kwargs: dict[str, str] = field(default_factory=dict, hash=False)

    @property
    def short_class(self) -> str:
        """The class name without its module path, e.g. ``LasBasler``."""
        return self.device_class.rsplit(".", 1)[-1]

    def template_values(self) -> dict[str, str]:
        """Values available to the ``{...}`` templates in device_types.yaml: the fields and the happi kwargs."""
        return {
            **self.kwargs,
            "name": self.name,
            "prefix": self.prefix,
            "prefix_nocolon": self.prefix.rstrip(":"),
            "doc": self.documentation,
        }


@dataclass
class DeviceType:
    """How to display one device class, loaded from device_types.yaml."""

    device_class: str
    screen: str = ""
    macros: dict[str, str] = field(default_factory=dict)
    indicator_pvs: list[str] = field(default_factory=list)

    def screen_path(self) -> str:
        """Absolute path to the screen file, or "" if there is none. Relative paths are relative to screens/."""
        if not self.screen:
            return ""
        path = Path(self.screen)
        if not path.is_absolute():
            path = SCREENS_DIR / path
        return str(path)

    def macros_for(self, device: DeviceInfo) -> dict[str, str]:
        values = device.template_values()
        return {key: str(val).format(**values) for key, val in self.macros.items()}

    def indicator_channels_for(self, device: DeviceInfo) -> list[str]:
        values = device.template_values()
        channels = []
        for pv in self.indicator_pvs:
            address = pv.format(**values)
            if "://" not in address:
                address = "ca://" + address
            channels.append(address)
        return channels


def load_device_types(path: str | os.PathLike = DEFAULT_TYPES_FILE) -> dict[str, DeviceType]:
    """Load the device class configuration, keyed by full device_class string."""
    with open(path) as fd:
        raw = yaml.safe_load(fd) or {}
    return {
        device_class: DeviceType(
            device_class=device_class,
            screen=cfg.get("screen") or "",
            macros=dict(cfg.get("macros") or {}),
            indicator_pvs=list(cfg.get("indicator_pvs") or []),
        )
        for device_class, cfg in raw.items()
    }


def find_device_type(device: DeviceInfo, types: dict[str, DeviceType]) -> DeviceType | None:
    """Match on the full class path first, then on the bare class name."""
    if device.device_class in types:
        return types[device.device_class]
    for device_class, dtype in types.items():
        if device_class.rsplit(".", 1)[-1] == device.short_class:
            return dtype
    return None


def default_database_path() -> str:
    """
    Find the happi JSON database without importing happi.

    Order: $LAS_DEVICE_DB, then the ``path`` in $HAPPI_CFG (or the shared default happi.cfg).
    """
    return os.environ.get("LAS_DEVICE_DB") or happi_database_path()


def happi_database_path() -> str:
    """The happi JSON database from $HAPPI_CFG (or the shared default happi.cfg), ignoring $LAS_DEVICE_DB."""
    cfg_path = os.environ.get("HAPPI_CFG", DEFAULT_HAPPI_CFG)
    parser = configparser.ConfigParser()
    if not parser.read(cfg_path):
        raise FileNotFoundError(f"Could not read happi config {cfg_path}")
    return parser["DEFAULT"]["path"]


def _render_kwargs(entry: dict[str, Any]) -> dict[str, str]:
    """happi kwargs with ``{{field}}`` filled in from the entry (a no-op for snapshot entries)."""
    return {
        key: HAPPI_TEMPLATE.sub(lambda match: str(entry.get(match.group(1)) or ""), str(value))
        for key, value in (entry.get("kwargs") or {}).items()
        if key != "name"
    }


def _entry_to_info(entry: dict[str, Any]) -> DeviceInfo:
    return DeviceInfo(
        name=entry["name"],
        device_class=entry.get("device_class", ""),
        prefix=entry.get("prefix") or "",
        location_group=entry.get(LOCATION_KEY) or "",
        functional_group=entry.get(FUNCTION_KEY) or "",
        documentation=entry.get("documentation") or "",
        kwargs=_render_kwargs(entry),
    )


def load_devices(beamline: str, path: str | os.PathLike | None = None) -> list[DeviceInfo]:
    """
    Load all active devices for a beamline.

    ``path`` may be a happi JSON database (filtered like ``cli.search(beamline=..., active=True)``)
    or a YAML snapshot written by ``tools/export_happi_devices.py`` (used as-is).
    """
    if path is None:
        path = default_database_path()
    path = Path(path)
    if path.suffix in (".yaml", ".yml"):
        with open(path) as fd:
            raw = yaml.safe_load(fd) or []
        return [_entry_to_info(entry) for entry in raw]

    with open(path) as fd:
        database = json.load(fd)
    return [
        _entry_to_info(entry)
        for entry in database.values()
        if str(entry.get("beamline", "")).upper() == beamline.upper() and entry.get("active", False)
    ]


def find_device(name: str, path: str | os.PathLike | None = None) -> DeviceInfo:
    """Look up a single device by name, from any beamline (used by open_device.py)."""
    if path is None:
        path = default_database_path()
    path = Path(path)
    with open(path) as fd:
        if path.suffix in (".yaml", ".yml"):
            entries = yaml.safe_load(fd) or []
        else:
            entries = list(json.load(fd).values())
    for entry in entries:
        if entry.get("name") == name:
            return _entry_to_info(entry)
    raise KeyError(f"No device named {name} in {path}")


def group_devices(devices: list[DeviceInfo]) -> dict[str, list[DeviceInfo]]:
    """
    Group devices into the ``"{location_group}|{functional_group}"`` dict that IndicatorGrid expects.

    Devices missing either key are skipped, the same as LUCID's HappiLoader.
    """
    groups: dict[str, list[DeviceInfo]] = {}
    for device in devices:
        if not device.location_group or not device.functional_group:
            logger.error("Device %s is missing %s or %s, skipping", device.name, LOCATION_KEY, FUNCTION_KEY)
            continue
        groups.setdefault(f"{device.location_group}|{device.functional_group}", []).append(device)
    return groups


def load_screen(path: str | os.PathLike, macros: dict[str, str], title: str) -> QWidget:
    """Build a pydm screen for the dock: in this process, hidden until shown, with pydm's stylesheet."""
    from pydm.display import ScreenTarget, load_file
    from pydm.utilities.stylesheet import merge_widget_stylesheet

    display = load_file(str(path), macros=macros, target=ScreenTarget.DIALOG)
    display.hide()
    merge_widget_stylesheet(widget=display)
    display.setWindowTitle(title)
    return display


def fallback_display(device: DeviceInfo, reason: str) -> QWidget:
    """A placeholder for devices that do not have a screen yet."""
    from qtpy.QtCore import Qt
    from qtpy.QtWidgets import QLabel, QVBoxLayout, QWidget

    widget = QWidget()
    widget.setWindowTitle(device.name)
    layout = QVBoxLayout()
    label = QLabel(
        f"<b>{device.name}</b><br>"
        f"class: {device.device_class}<br>"
        f"prefix: {device.prefix or '(none)'}<br>"
        f"location: {device.location_group} / {device.functional_group}<br><br>"
        f"{reason}"
    )
    label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    label.setWordWrap(True)
    layout.addWidget(label)
    layout.addStretch()
    widget.setLayout(layout)
    return widget


class DeviceScreenCache:
    """Builds and caches the pydm screen for each device (the stand-in for typhos' display_for_device)."""

    def __init__(self, types: dict[str, DeviceType]):
        self.types = types
        self._cache: dict[str, QWidget] = {}

    def display_for_device(self, device: DeviceInfo) -> QWidget:
        if device.name in self._cache:
            return self._cache[device.name]
        dtype = find_device_type(device, self.types)
        path = dtype.screen_path() if dtype is not None else ""
        if dtype is None:
            display = fallback_display(device, "No screen is configured for this device class yet.")
        elif not path:
            display = fallback_display(device, "This device class has no screen in config/device_types.yaml.")
        elif not os.path.isfile(path):
            display = fallback_display(device, f"Screen file not found:<br>{path}")
        else:
            logger.debug("Creating display for %s from %s", device.name, path)
            display = load_screen(path, dtype.macros_for(device), device.name)
        self._cache[device.name] = display
        return display
