import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from alarm import AlarmLevel, PVAlarmCircle
from devices import (
    DeviceInfo,
    _entry_to_info,
    find_device,
    find_device_type,
    group_devices,
    load_device_types,
    load_devices,
)
from grid import GridAlarmCircle, LasIndicatorGrid, PVIndicatorCell
from pydm.display import ScreenTarget, load_file
from pydm.widgets import PyDMEmbeddedDisplay
from pyqtgraph import GraphicsView
from pytestqt.qtbot import QtBot
from qtpy.QtWidgets import QWidget

APP_DIR = Path(__file__).resolve().parent.parent
FORBIDDEN = ("happi", "ophyd", "pcdsdevices", "typhos", "lucid")
CAM = {"CAM": "LAS:LHN:BAY1:CAM:02", "NAME": "cam", "DESC": "Bay 1 cam"}

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
    assert find_device("c", path).name == "c"
    with pytest.raises(KeyError):
        find_device("nope", path)


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
    types = load_device_types()
    for device in load_devices("LAS"):
        dtype = find_device_type(device, types)
        assert dtype is not None, device
        assert Path(dtype.screen_path()).is_file(), dtype.screen_path()
        assert dtype.indicator_pvs, device


def test_device_types_point_at_local_screens():
    """Every configured screen is in this directory and exists."""
    types = load_device_types()
    assert types["pcdsdevices.epics_motor.SmarAct"].screen_path() == str(APP_DIR / "screens" / "smaract.py")
    assert types["pcdsdevices.epics_motor.SmarAct"].indicator_pvs == ["{prefix}.RBV"]
    assert len(types["pcdsdevices.lasers.btps.BtpsState"].indicator_pvs) == 732
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
        ("btps/btps.ui", {}),
    ],
)
def test_screens_load_with_all_macros_filled(qtbot: QtBot, screen: str, macros: dict[str, str]):
    display = load_file(str(APP_DIR / "screens" / screen), macros=macros, target=ScreenTarget.DIALOG)
    add_widget(qtbot, display)
    # Embedded displays load lazily (hidden BTPS tabs only when shown); force them so their macros are checked too
    for child in display.findChildren(PyDMEmbeddedDisplay):
        child.loadWhenShown = False
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


def test_btps_screens_have_no_typhos_commands():
    for path in (APP_DIR / "screens" / "btps").glob("*.ui"):
        assert not re.search(r"<string>typhos ", path.read_text()), path


def test_grid_builds_from_snapshot(qtbot: QtBot):
    grid = LasIndicatorGrid()
    qtbot.addWidget(grid)
    grid.beamline = "LAS"
    cells = grid.findChildren(PVIndicatorCell)
    indicators = grid.findChildren(GridAlarmCircle)
    assert len(grid.devices) == 44
    assert len(indicators) == 44
    assert sum(len(cell.devices) for cell in cells) == 44


def test_grid_opens_pydm_screen(qtbot: QtBot):
    grid = LasIndicatorGrid()
    qtbot.addWidget(grid)
    grid.beamline = "LAS"
    cell = next(cell for cell in grid.findChildren(PVIndicatorCell) if cell.devices)
    device = cell.devices[0]
    widget = cell.show_device(device)
    add_widget(qtbot, widget)
    assert widget.windowTitle() == device.name
    assert cell.show_device(device) is widget


def test_unknown_class_gets_placeholder(qtbot: QtBot):
    grid = LasIndicatorGrid()
    qtbot.addWidget(grid)
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


def test_open_device_prints_pydm_command():
    result = subprocess.run(
        [sys.executable, str(APP_DIR / "open_device.py"), "--print", "las_bts_mcs2_01_m1"],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [str(APP_DIR), os.environ.get("PYTHONPATH")]))},
    )
    assert "smaract.py" in result.stdout
    assert '"MOTOR": "LAS:BTS:MCS2:01:m1"' in result.stdout


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
