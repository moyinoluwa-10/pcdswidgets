"""``FloorPlanContext``: a location's floorplan.yaml, toolbar and happi devices, turned into Openers."""

import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml
from devices import DeviceInfo, DeviceScreenCache, find_device_type, load_device_types, load_devices, load_screen
from openers import DockScreen, Opener
from pdu import RACK_IN_NAME, pdu_macros
from qtpy.QtWidgets import QWidget

PACKAGE_DIR = Path(__file__).resolve().parent
# happi functional_group -> menu title and icon, for every location
FUNCTIONS_FILE = PACKAGE_DIR / "config" / "functions.yaml"
SCREENS_DIR = PACKAGE_DIR / "screens"
PDU_SCREEN = "pdu_tripplite.py"

logger = logging.getLogger(__name__)


class FloorPlanContext:
    """Loads the configs once and turns ``opens`` entries into Openers."""

    def __init__(
        self,
        config_file: str | os.PathLike,
        toolbar_file: str | os.PathLike | None = None,
        device_db: str | os.PathLike | None = None,
        beamline: str | None = None,
    ):
        """
        ``config_file``: the location's floorplan.yaml. The toolbar and beamline default to its ``toolbar``
        (absolute, or relative to it) and ``beamline`` entries.
        """
        self.config_file = Path(config_file).resolve()
        with open(self.config_file) as fd:
            self.config: dict[str, Any] = yaml.safe_load(fd)
        self.beamline = beamline or self.config["beamline"]
        self.title = self.config.get("title") or f"{self.beamline} Home"
        self.toolbar_file = Path(toolbar_file) if toolbar_file else self.config_file.parent / self.config["toolbar"]
        # A location's own screens (next to its floorplan.yaml), for screens only it uses
        self.location_screens = self.config_file.parent / "screens"
        with open(self.toolbar_file) as fd:
            self.toolbar: dict[str, Any] = yaml.safe_load(fd) or {}
        self.devices = load_devices(self.beamline, device_db)
        self.devices_by_name = {dev.name: dev for dev in self.devices}
        self.types = load_device_types()
        self.screens = DeviceScreenCache(self.types)
        self._screen_cache: dict[str, QWidget] = {}
        self._dock_screens: dict[str, DockScreen] = {}
        # happi functional_group -> menu title and icon: the package's, plus or overridden by the location's
        with open(FUNCTIONS_FILE) as fd:
            self.functions: dict[str, dict[str, str]] = {**yaml.safe_load(fd), **self.config.get("functions", {})}
        self.shutters: dict[str, dict[str, str]] = self.config.get("shutters", {})

    def dock_screen(self, key: str, make: Callable[[], QWidget]) -> DockScreen:
        """The screen for ``key`` in its DockScreen, built once and shared by every opener of it."""
        if key not in self._dock_screens:
            self._dock_screens[key] = DockScreen(make())
        return self._dock_screens[key]

    # Openers for each kind of entry

    def device_opener(self, device: DeviceInfo, title: str = "") -> Opener:
        dtype = find_device_type(device, self.types)
        function = self.functions.get(device.functional_group, {})
        return Opener(
            title=title or device.name,
            icon=function.get("icon", "cube"),
            build=lambda: self.dock_screen(f"device|{device.name}", lambda: self.screens.display_for_device(device)),
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
                    icon=cfg.get("icon", "cube"),
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

    def find_screen(self, screen: str) -> Path:
        """A screen named in floorplan.yaml: absolute, in the location's own screens/, or in this package's."""
        path = Path(screen)
        if path.is_absolute():
            return path
        if (self.location_screens / path).is_file():
            return self.location_screens / path
        return SCREENS_DIR / path

    def screen_opener(self, entry: dict[str, Any], icon: str = "window-maximize") -> Opener:
        path = self.find_screen(entry["screen"])
        macros = {key: str(val) for key, val in (entry.get("macros") or {}).items()}
        title = entry.get("title") or path.stem
        key = f"{path}|{sorted(macros.items())}"

        def build() -> QWidget:
            if key not in self._screen_cache:
                self._screen_cache[key] = load_screen(path, macros, title)
            return self.dock_screen(f"screen|{key}", lambda: self._screen_cache[key])

        return Opener(title=title, icon=entry.get("icon", icon), build=build, tooltip=str(path))

    def toolbar_opener(self, tab: str, button: str, title: str = "") -> Opener:
        """
        A LUCID-style toolbar button. A button with several ``commands`` and ``titles`` is a menu in the
        toolbar: pass ``title`` to pick one of them, or get a group with one opener per command.
        """
        try:
            cfg = self.toolbar[tab]["buttons"][button]
            commands = list(cfg["commands"])
            titles = list(cfg.get("titles") or [])
            if title:
                commands = [commands[titles.index(title)]]
        except (KeyError, ValueError):
            logger.error("No toolbar button %r %r in tab %r", button, title, tab)
            return Opener(title=f"{title or button} (missing)", icon="exclamation-triangle")
        external = {"icon": "external", "tooltip": "Opens in its own window"}
        if not title and len(titles) == len(commands) > 1:
            children = [
                Opener(title=name, command=[command], **external)
                for name, command in zip(titles, commands, strict=True)
            ]
            return Opener(title=button, icon="external", children=children)
        return Opener(title=title or button, command=commands, **external)

    def rack_openers(self, rack: str, cfg: dict[str, Any]) -> list[Opener]:
        """
        What a rack opens: its own ``opens`` list if it has one, otherwise every button in the
        toolbar's rack tab (the "PDUs" tab) whose name ends with the rack in parentheses, e.g. "... (R07)".
        A TrippLite PDU button opens screens/pdu_tripplite.py in the dock; any other button runs its command.
        """
        if "opens" in cfg:
            return self.resolve(cfg["opens"])
        tab = self.config.get("rack_toolbar_tab", "PDUs")
        buttons = self.toolbar.get(tab, {}).get("buttons", {})
        return [
            self.pdu_opener(tab, name)
            for name in buttons
            if (match := RACK_IN_NAME.search(name)) is not None and match.group(1) == rack
        ]

    def pdu_opener(self, tab: str, button: str) -> Opener:
        """
        The pdu_tripplite.py screen for a toolbar PDU button, with the PV prefix and outlet count that its
        EDM launch uses (``-m PRE=...`` and ``TrippLite_N.edl``, in the command or in the .cmd script it runs).
        Falls back to the toolbar button itself (the EDM screen) when they can't be found.
        """
        commands = (self.toolbar.get(tab, {}).get("buttons", {}).get(button) or {}).get("commands") or []
        pdu = pdu_macros(commands)
        if pdu is None:
            return self.toolbar_opener(tab, button)
        entry = {"screen": PDU_SCREEN, "macros": {**pdu, "TITLE": button}, "title": button, "icon": "pdu"}
        return self.screen_opener(entry)

    def resolve(self, entries: list[dict[str, Any]]) -> list[Opener]:
        """Turn an ``opens`` list from the config into Openers."""
        openers = []
        for entry in entries:
            if "device" in entry:
                device = self.devices_by_name.get(entry["device"])
                if device is None:
                    logger.error("Device %s is not an active %s device", entry["device"], self.beamline)
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

    def station_openers(self, station: str, cfg: dict[str, Any]) -> list[Opener]:
        """Every control in a station (MODS): devices by function, then external tools."""
        openers = self.function_groups(self.devices_matching(cfg.get("locations", [station])))
        tools = [self.toolbar_opener(*tool) for tool in cfg.get("tools", [])]
        if tools:
            openers.append(Opener(title="Tools", icon="tools", children=tools))
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
            openers.append(Opener(title="Shutters", icon="shutter", children=shutters))
        tools = [self.toolbar_opener(*tool) for tool in cfg.get("tools", [])]
        if tools:
            openers.append(Opener(title="Tools", icon="tools", children=tools))
        return openers
