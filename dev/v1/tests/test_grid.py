import json
import os
import subprocess
import sys
from pathlib import Path

import grid as grid_module
import pytest
from alarm import AlarmLevel, PVAlarmCircle
from devices import (
    DeviceInfo,
    _entry_to_info,
    find_device_type,
    group_devices,
    load_device_types,
    load_devices,
)
from grid import DockScreen, GridAlarmCircle, LasIndicatorGrid, PVIndicatorCell, PVIndicatorGroup, load_toolbar_tools
from pydm.display import ScreenTarget, load_file
from pydm.widgets import PyDMEmbeddedDisplay
from pyqtgraph import GraphicsView
from pytestqt.qtbot import QtBot
from qtpy.QtCore import QEvent, QPoint, Qt
from qtpy.QtGui import QMouseEvent
from qtpy.QtWidgets import QLabel, QWidget

from pcdswidgets.common.dock.tab_dock import TabDock

APP_DIR = Path(__file__).resolve().parent.parent
FORBIDDEN = ("happi", "ophyd", "pcdsdevices", "typhos", "lucid")
CAM = {"CAM": "LAS:LHN:BAY1:CAM:02", "NAME": "cam", "DESC": "Bay 1 cam"}
RUN_BTPS = "/cds/group/pcds/epics-dev/screens/pydm/las/bts/run_btps.sh"


@pytest.fixture(autouse=True)
def no_external_commands(monkeypatch):
    """Never launch the BTPS or other external tools from the tests."""
    launched = []
    monkeypatch.setattr(grid_module, "run_command", lambda commands: launched.extend(commands))
    return launched


@pytest.fixture
def grid(qtbot: QtBot) -> LasIndicatorGrid:
    widget = LasIndicatorGrid()
    qtbot.addWidget(widget)
    widget.beamline = "LAS"
    return widget


def press(widget: QWidget, button=Qt.LeftButton) -> bool:
    """Send a mouse press through the widget's event filter, as a click on it (or its indicator) does."""
    event = QMouseEvent(QEvent.MouseButtonPress, QPoint(2, 2), button, button, Qt.NoModifier)
    return widget.eventFilter(widget, event)


# Screens with pyqtgraph views (the camera image) live for the whole session:
# deleting one mid-session can segfault in pyqtgraph's named-ViewBox "destroyed" handler, in a later test.
_PLOT_SCREENS: list[QWidget] = []


def add_widget(qtbot: QtBot, widget: QWidget) -> None:
    """qtbot.addWidget, except screens with pyqtgraph views are kept (hidden) instead of being deleted."""
    if widget.findChildren(GraphicsView):
        _PLOT_SCREENS.append(widget)
        widget.hide()
    else:
        qtbot.addWidget(widget)


def channel_addresses(widget: QWidget) -> set[str]:
    addresses = set()
    for child in [widget, *widget.findChildren(QWidget)]:
        channels = getattr(child, "channels", None)
        if callable(channels):
            addresses.update(ch.address for ch in channels() or [] if getattr(ch, "address", None))
    return addresses


def test_snapshot_matches_lucid_grouping():
    devices = load_devices("LAS")
    assert len(devices) == 44
    groups = group_devices(devices)
    rows = {key.split("|")[0] for key in groups}
    cols = {key.split("|")[1] for key in groups}
    assert rows == {"Bay 1", "Bay 2", "Bay 2 - 1um", "Bay 2 - 800nm", "Bay 3", "Bay 4", "Beam Transport"}
    assert cols == {"BTPS", "cameras", "env sensors", "smaract"}


def test_json_database_filters_like_happi_search(tmp_path):
    db = {
        "a": {"name": "a", "beamline": "LAS", "active": True, "device_class": "x.A", "location_group": "L"},
        "b": {"name": "b", "beamline": "LAS", "active": False, "device_class": "x.A"},
        "c": {"name": "c", "beamline": "TMO", "active": True, "device_class": "x.A"},
        "d": {"name": "d", "beamline": "las", "active": True, "device_class": "x.A", "prefix": None},
    }
    path = tmp_path / "db.json"
    path.write_text(json.dumps(db))
    assert [dev.name for dev in load_devices("LAS", path)] == ["a", "d"]
    assert load_devices("LAS", path)[1].prefix == ""


def test_group_devices_skips_missing_keys():
    devices = [
        DeviceInfo(name="ok", device_class="x.A", location_group="L", functional_group="F"),
        DeviceInfo(name="no_col", device_class="x.A", location_group="L"),
    ]
    assert group_devices(devices) == {"L|F": [devices[0]]}


def test_happi_kwargs_are_filled_in_from_the_entry():
    entry = {
        "name": "tt",
        "device_class": "pcdsdevices.epics_motor.SmarActTipTilt",
        "prefix": "LAS:X",
        "ioc_tip_suffix": "_TIP1",
        "kwargs": {"name": "{{name}}", "tip_pv": "{{ioc_tip_suffix}}", "port": "15"},
    }
    info = _entry_to_info(entry)
    assert info.kwargs == {"tip_pv": "_TIP1", "port": "15"}
    assert info.template_values()["tip_pv"] == "_TIP1"


def test_every_las_device_has_a_screen():
    """Every device opens a screen, except the toolbar devices (the BTPS), which run a toolbar button."""
    types = load_device_types()
    tools = load_toolbar_tools()
    assert list(tools) == ["las_btps"]
    for device in load_devices("LAS"):
        if device.name in tools:
            assert find_device_type(device, types) is None, device
            continue
        dtype = find_device_type(device, types)
        assert dtype is not None, device
        assert Path(dtype.screen_path()).is_file(), dtype.screen_path()
        assert dtype.indicator_pvs, device


def test_device_types_point_at_local_screens():
    """Every configured screen is in this directory and exists."""
    types = load_device_types()
    assert types["pcdsdevices.epics_motor.SmarAct"].screen_path() == str(APP_DIR / "screens" / "smaract.py")
    assert types["pcdsdevices.epics_motor.SmarAct"].indicator_pvs == ["{prefix}.RBV"]
    # The BTPS runs the toolbar's "BTPS Overview" and has no status dot, so it has no device type (as in dev/las)
    assert "pcdsdevices.lasers.btps.BtpsState" not in types
    for dtype in types.values():
        assert Path(dtype.screen_path()).is_relative_to(APP_DIR), dtype.device_class


def test_template_values():
    device = DeviceInfo(name="cam", device_class="x.LasBasler", prefix="LAS:CAM:01:")
    dtype = load_device_types()["pcdsdevices.areadetector.detectors.LasBasler"]
    assert dtype.macros_for(device)["CAM"] == "LAS:CAM:01"
    assert "ca://LAS:CAM:01:DetectorState_RBV" in dtype.indicator_channels_for(device)


def test_find_device_type_by_short_name():
    types = load_device_types()
    device = DeviceInfo(name="m", device_class="some.other.module.SmarAct")
    assert find_device_type(device, types) is types["pcdsdevices.epics_motor.SmarAct"]


@pytest.mark.parametrize(
    "screen,macros",
    [
        ("las_basler.ui", CAM),
        ("las_basler_settings.ui", {"CAM": CAM["CAM"]}),
        ("smaract.py", {"MOTOR": "LAS:BTS:MCS2:01:m1", "NAME": "m1"}),
        ("env_monitor.ui", {"PREFIX": "LAS:LHN:ADC:01:BHC:AI2", "NAME": "env"}),
    ],
)
def test_screens_load_with_all_macros_filled(qtbot: QtBot, screen: str, macros: dict[str, str]):
    display = load_file(str(APP_DIR / "screens" / screen), macros=macros, target=ScreenTarget.DIALOG)
    add_widget(qtbot, display)
    # Embedded displays load lazily; force them so their macros are checked too
    for child in display.findChildren(PyDMEmbeddedDisplay):
        child.load_if_needed()
        assert child.embedded_widget is not None, child.filename
    addresses = channel_addresses(display)
    assert addresses
    assert not [addr for addr in addresses if "${" in addr]


def test_camera_screen_has_the_settings_panel(qtbot: QtBot):
    display = load_file(str(APP_DIR / "screens" / "las_basler.ui"), macros=CAM, target=ScreenTarget.DIALOG)
    add_widget(qtbot, display)
    embedded = display.findChildren(PyDMEmbeddedDisplay)
    assert [child.objectName() for child in embedded] == ["las_settings"]
    embedded[0].load_if_needed()
    assert "ca://LAS:LHN:BAY1:CAM:02:RESET.PROC" in channel_addresses(display)


def test_smaract_screen_has_expert_and_advanced_panels(qtbot: QtBot):
    display = load_file(
        str(APP_DIR / "screens" / "smaract.py"),
        macros={"MOTOR": "LAS:BTS:MCS2:01:m1", "NAME": "las_bts_mcs2_01_m1"},
        target=ScreenTarget.DIALOG,
    )
    add_widget(qtbot, display)
    tabs = display.advanced.tabWidget
    assert [tabs.tabText(i) for i in range(tabs.count())] == [
        "Open-loop",
        "Closed-loop",
        "Diagnostics",
        "Configuration",
    ]
    assert "ca://LAS:BTS:MCS2:01:m1:STATE_RBV" in channel_addresses(display)
    assert display.windowTitle() == "las_bts_mcs2_01_m1"


def test_grid_builds_from_snapshot(grid: LasIndicatorGrid):
    cells = grid.findChildren(PVIndicatorCell)
    assert len(grid.devices) == 44
    assert sum(len(cell.devices) for cell in cells) == 44
    # Every device but the BTPS has a status dot, with a thin black outline as in dev/las
    dots = grid.findChildren(GridAlarmCircle)
    assert len(dots) == 43
    assert all(
        dot.penStyle == Qt.SolidLine and dot.penColor.name() == "#000000" and dot.penWidth == 1.5 for dot in dots
    )


def test_grid_opens_pydm_screen(qtbot: QtBot, grid: LasIndicatorGrid):
    cell = next(
        cell
        for cell in grid.findChildren(PVIndicatorCell)
        if cell.devices and not cell.tools.keys() & {device.name for device in cell.devices}
    )
    device = cell.devices[0]
    widget = cell.show_device(device)
    add_widget(qtbot, widget)
    assert widget.windowTitle() == device.name
    # Docked in a scroll area holding the pydm screen; the same one every time (cells and menus share it)
    assert isinstance(widget, DockScreen) and widget.widget() is widget.display
    assert cell.show_device(device) is widget


def test_btps_cell_runs_the_toolbar_command(grid: LasIndicatorGrid, no_external_commands):
    """As in dev/las: no status dot, and a click runs the toolbar's "BTPS Overview" in its own window."""
    cell = next(cell for cell in grid.findChildren(PVIndicatorCell) if [d.name for d in cell.devices] == ["las_btps"])
    assert not cell.findChildren(GridAlarmCircle)
    assert cell.findChildren(QLabel)
    assert press(cell)
    assert no_external_commands == [RUN_BTPS]
    # Its row header (the BTPS row has only the BTPS) does the same
    row = next(group for group in grid.findChildren(PVIndicatorGroup) if group.title == "BTPS")
    assert press(row)
    assert no_external_commands == [RUN_BTPS, RUN_BTPS]


def test_btps_is_an_external_entry_in_menus(qtbot: QtBot, grid: LasIndicatorGrid, no_external_commands):
    """The Bay 1 column menu lists the BTPS as an external entry, and "Open All" leaves it out."""
    # The menus' dock entries need a TabDock, as in the home screen
    dock = TabDock()
    qtbot.addWidget(dock)
    bay1 = next(group for group in grid.findChildren(PVIndicatorGroup) if group.title == "Bay 1")
    assert "las_btps" in [device.name for device in bay1.devices]
    assert "las_btps" not in bay1.get_all_titles()
    bay1._menu_shown()
    actions = {action.text(): action for action in bay1.device_menu.actions()}
    assert "Open All" in actions and "las_btps" not in actions
    actions["BTPS Overview \u2197"].trigger()
    assert no_external_commands == [RUN_BTPS]
    # Showing the menu again doesn't add duplicates
    bay1._menu_shown()
    assert [action.text() for action in bay1.device_menu.actions()].count("BTPS Overview \u2197") == 1


def test_missing_toolbar_button_runs_nothing(tmp_path):
    toolbar = tmp_path / "toolbar.yaml"
    toolbar.write_text("Tools:\n  buttons: {}\n")
    assert load_toolbar_tools(toolbar)["las_btps"].commands == []


def test_unknown_class_gets_placeholder(qtbot: QtBot, grid: LasIndicatorGrid):
    device = DeviceInfo(name="mystery", device_class="x.Unknown", location_group="L", functional_group="F")
    widget = grid.screens.display_for_device(device)
    qtbot.addWidget(widget)
    assert widget.windowTitle() == "mystery"


def test_alarm_circle_summary(qtbot: QtBot):
    circle = PVAlarmCircle(channels=["ca://A", "ca://B"])
    qtbot.addWidget(circle)
    assert circle.alarm_summary == AlarmLevel.DISCONNECTED
    for address in ("ca://A", "ca://B"):
        circle.update_connection(True, address)
        circle.update_severity(0, address)
    assert circle.alarm_summary == AlarmLevel.NO_ALARM
    assert circle.alarm_tooltip() == ""
    circle.update_severity(2, "ca://B")
    assert circle.alarm_summary == AlarmLevel.MAJOR
    assert "B: MAJOR" in circle.alarm_tooltip()
    circle.update_connection(False, "ca://A")
    assert circle.alarm_summary == AlarmLevel.DISCONNECTED
    assert "rgba(255,255,255,255)" in circle.styleSheet()


def test_grid_cell_tooltip_names_the_device(qtbot: QtBot):
    circle = GridAlarmCircle(channels=["ca://A"], title="las_cam")
    qtbot.addWidget(circle)
    assert circle.cell_tooltip().splitlines()[0] == "Device las_cam"
    assert "A: DISCONNECTED" in circle.cell_tooltip()
    circle.update_connection(True, "ca://A")
    circle.update_severity(0, "ca://A")
    assert circle.cell_tooltip() == "Device las_cam"


def test_home_screen_imports_nothing_forbidden():
    """Load the full home screen in a fresh interpreter: nothing forbidden, nothing from the rest of dev/."""
    script = (
        "import os, sys\n"
        "from pydm import PyDMApplication\n"
        "from pydm.display import load_file\n"
        "app = PyDMApplication(hide_nav_bar=True, hide_menu_bar=True, hide_status_bar=True)\n"
        # target=None loads in this process; the default (NEW_PROCESS) would spawn a separate pydm.
        f"display = load_file({str(APP_DIR / 'las_home.py')!r}, target=None)\n"
        "assert len(display.grid.devices) == 44\n"
        "assert display.toolbar.tab.count() == 10\n"
        f"bad = sorted(m for m in sys.modules if m.split('.')[0] in {FORBIDDEN!r})\n"
        "print('FORBIDDEN', bad)\n"
        f"dev_dir, app_dir = {str(APP_DIR.parent) + os.sep!r}, {str(APP_DIR) + os.sep!r}\n"
        "files = [getattr(mod, '__file__', '') or '' for mod in list(sys.modules.values())]\n"
        "outside = sorted(f for f in files if f.startswith(dev_dir) and not f.startswith(app_dir))\n"
        "print('OUTSIDE', outside)\n"
        "sys.stdout.flush()\n"
        "os._exit(0)\n"
    )
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(filter(None, [str(APP_DIR), os.environ.get("PYTHONPATH", "")])),
        "QT_QPA_PLATFORM": "offscreen",
    }
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env, timeout=120)
    assert "FORBIDDEN []" in result.stdout, result.stdout + result.stderr[-2000:]
    assert "OUTSIDE []" in result.stdout, result.stdout


def test_dock_is_visible_at_launch():
    """Launched the way las_home.sh does (pydm main window), the window opens wide enough to show the dock."""
    script = (
        "import os, sys\n"
        "from pydm import PyDMApplication\n"
        f"app = PyDMApplication(ui_file={str(APP_DIR / 'las_home.py')!r}, hide_nav_bar=True, hide_menu_bar=True,"
        " hide_status_bar=True)\n"
        "for _ in range(50):\n"
        "    app.processEvents()\n"
        "home = app.main_window.display_widget()\n"
        "print('DOCK', home.dock.isVisible(), home.dummy_tabs.isVisible(), home.width() >= home.width_threshold)\n"
        "sys.stdout.flush()\n"
        "os._exit(0)\n"
    )
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(filter(None, [str(APP_DIR), os.environ.get("PYTHONPATH", "")])),
        "QT_QPA_PLATFORM": "offscreen",
    }
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env, timeout=120)
    assert "DOCK True False True" in result.stdout, result.stdout + result.stderr[-2000:]


def test_tall_screens_scroll_in_the_dock():
    """SmarAct and camera screens are taller than the dock at launch: they scroll at full height, not squashed."""
    script = (
        "import os, sys\n"
        "from pydm import PyDMApplication\n"
        "from pcdswidgets.common.dock.tab_dock import TabDock\n"
        f"app = PyDMApplication(ui_file={str(APP_DIR / 'las_home.py')!r}, hide_nav_bar=True, hide_menu_bar=True,"
        " hide_status_bar=True)\n"
        "for _ in range(50):\n"
        "    app.processEvents()\n"
        "home = app.main_window.display_widget()\n"
        "devices = {d.name: d for d in home.grid.devices}\n"
        "for name in ('las_bts_mcs2_01_m1', 'las_lhn_bay1_cam_nf'):\n"
        "    screen = home.grid.screens.display_for_device(devices[name])\n"
        "    TabDock.add_to_dock(widget=screen, title=name, new_tab=True)\n"
        "    for _ in range(20):\n"
        "        app.processEvents()\n"
        "    full = screen.display.height() >= screen.display.minimumSizeHint().height()\n"
        "    scrolls = screen.verticalScrollBar().maximum() > 0\n"
        "    print('SCREEN', name, full, scrolls, screen.height() < screen.display.height())\n"
        "sys.stdout.flush()\n"
        "os._exit(0)\n"
    )
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(filter(None, [str(APP_DIR), os.environ.get("PYTHONPATH", "")])),
        "QT_QPA_PLATFORM": "offscreen",
    }
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env, timeout=120)
    for name in ("las_bts_mcs2_01_m1", "las_lhn_bay1_cam_nf"):
        assert f"SCREEN {name} True True True" in result.stdout, result.stdout + result.stderr[-2000:]
