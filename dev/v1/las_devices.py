"""
Device list loading for the LAS home screen, without happi, ophyd, or pcdsdevices.

LUCID builds its grid by asking happi for every active device on a beamline and
instantiating each entry as an ophyd device. Here we only need a handful of
metadata fields per device, so we read the happi JSON database as plain JSON
(or a YAML snapshot exported from it) and never import happi itself.

The per-class behavior (which screen to open, which macros to pass, which PVs
summarize the alarm state) lives in ``config/device_types.yaml``.
"""

import configparser
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

DEV_DIR = Path(__file__).resolve().parent
CONFIG_DIR = DEV_DIR / "config"
SCREENS_DIR = DEV_DIR / "screens"
DEFAULT_TYPES_FILE = CONFIG_DIR / "device_types.yaml"
DEFAULT_HAPPI_CFG = "/cds/group/pcds/pyps/apps/hutch-python/device_config/happi.cfg"

ROW_GROUP_KEY = "location_group"
COL_GROUP_KEY = "functional_group"


@dataclass(frozen=True)
class DeviceInfo:
    """The subset of a happi entry that the home screen needs."""

    name: str
    device_class: str
    prefix: str = ""
    location_group: str = ""
    functional_group: str = ""
    documentation: str = ""

    @property
    def short_class(self) -> str:
        """The class name without its module path, e.g. ``LasBasler``."""
        return self.device_class.rsplit(".", 1)[-1]

    def template_values(self) -> dict[str, str]:
        """Values available to the ``{...}`` templates in device_types.yaml."""
        return {
            "name": self.name,
            "prefix": self.prefix,
            "prefix_nocolon": self.prefix.rstrip(":"),
            "doc": self.documentation,
            "dev": str(DEV_DIR),
        }


@dataclass
class DeviceType:
    """How to display one device class, loaded from device_types.yaml."""

    device_class: str
    screen: str
    macros: dict[str, str] = field(default_factory=dict)
    indicator_pvs: list[str] = field(default_factory=list)

    def screen_path(self) -> str:
        """Absolute path to the screen file. Relative paths are relative to the screens dir."""
        path = Path(self.screen.format(dev=str(DEV_DIR)))
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
    types = {}
    for device_class, cfg in raw.items():
        types[device_class] = DeviceType(
            device_class=device_class,
            screen=cfg["screen"],
            macros=dict(cfg.get("macros") or {}),
            indicator_pvs=list(cfg.get("indicator_pvs") or []),
        )
    return types


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
    env_db = os.environ.get("LAS_DEVICE_DB")
    if env_db:
        return env_db
    cfg_path = os.environ.get("HAPPI_CFG", DEFAULT_HAPPI_CFG)
    parser = configparser.ConfigParser()
    if not parser.read(cfg_path):
        raise FileNotFoundError(f"Could not read happi config {cfg_path}")
    return parser["DEFAULT"]["path"]


def _entry_to_info(entry: dict[str, Any]) -> DeviceInfo:
    return DeviceInfo(
        name=entry["name"],
        device_class=entry.get("device_class", ""),
        prefix=entry.get("prefix") or "",
        location_group=entry.get(ROW_GROUP_KEY) or "",
        functional_group=entry.get(COL_GROUP_KEY) or "",
        documentation=entry.get("documentation") or "",
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
    devices = []
    for entry in database.values():
        if str(entry.get("beamline", "")).upper() != beamline.upper():
            continue
        if not entry.get("active", False):
            continue
        devices.append(_entry_to_info(entry))
    return devices


def find_device(name: str, path: str | os.PathLike | None = None) -> DeviceInfo:
    """Look up a single device by name, from any beamline."""
    if path is None:
        path = default_database_path()
    path = Path(path)
    if path.suffix in (".yaml", ".yml"):
        with open(path) as fd:
            entries = yaml.safe_load(fd) or []
    else:
        with open(path) as fd:
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
            logger.error("Device %s is missing %s or %s, skipping", device.name, ROW_GROUP_KEY, COL_GROUP_KEY)
            continue
        groups.setdefault(f"{device.location_group}|{device.functional_group}", []).append(device)
    return groups
