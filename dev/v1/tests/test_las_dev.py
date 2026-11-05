import json
import re
import subprocess
import sys
from pathlib import Path

import las_devices
import pytest
from las_devices import DeviceInfo, find_device_type, group_devices, load_device_types, load_devices
from las_grid import AlarmLevel, LasIndicatorGrid, PVAlarmCircle, PVIndicatorCell
from pydm.display import ScreenTarget, load_file
from pytestqt.qtbot import QtBot
from qtpy.QtWidgets import QWidget

DEV_DIR = Path(__file__).resolve().parent.parent
FORBIDDEN = ("happi", "ophyd", "pcdsdevices", "typhos", "lucid")


def all_channel_addresses(widget: QWidget) -> set[str]:
    addresses = set()
    for child in [widget, *widget.findChildren(QWidget)]:
        channels = getattr(child, "channels", None)
        if not callable(channels):
            continue
        for channel in channels() or []:
            address = getattr(channel, "address", None)
            if address:
                addresses.add(address)
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


def test_every_las_device_has_a_screen():
    types = load_device_types()
    for device in load_devices("LAS"):
        dtype = find_device_type(device, types)
        assert dtype is not None, device
        assert Path(dtype.screen_path()).is_file(), dtype.screen_path()
        assert dtype.indicator_pvs, device


def test_template_values():
    device = DeviceInfo(name="cam", device_class="x.LasBasler", prefix="LAS:CAM:01:")
    dtype = load_device_types()["pcdsdevices.areadetector.detectors.LasBasler"]
    assert dtype.macros_for(device)["CAM"] == "LAS:CAM:01"
    assert "ca://LAS:CAM:01:DetectorState_RBV" in dtype.indicator_channels_for(device)


def test_find_device_type_by_short_name():
    types = load_device_types()
    device = DeviceInfo(name="m", device_class="some.other.module.SmarAct")
    assert find_device_type(device, types) is types["pcdsdevices.epics_motor.SmarAct"]


SCREEN_CASES = [
    ("las_basler.ui", {"CAM": "LAS:LHN:BAY1:CAM:02", "NAME": "cam", "DESC": "desc"}),
    ("smaract_detailed.ui", {"MOTOR": "LAS:BTS:MCS2:01:m1", "NAME": "m1"}),
    ("env_monitor.ui", {"PREFIX": "LAS:LHN:ADC:01:BHC:AI2", "NAME": "env"}),
    ("btps/btps.ui", {}),
]


@pytest.mark.parametrize("screen,macros", SCREEN_CASES)
def test_screens_load_with_all_macros_filled(qtbot: QtBot, screen: str, macros: dict[str, str]):
    display = load_file(str(DEV_DIR / "screens" / screen), macros=macros, target=ScreenTarget.DIALOG)
    qtbot.addWidget(display)
    addresses = all_channel_addresses(display)
    assert addresses
    assert not [addr for addr in addresses if "${" in addr]


def test_camera_sidebar_adopts_all_panels(qtbot: QtBot):
    display = load_file(
        str(DEV_DIR / "screens" / "las_basler.ui"),
        macros={"CAM": "LAS:LHN:BAY1:CAM:02", "NAME": "cam", "DESC": ""},
        target=ScreenTarget.DIALOG,
    )
    qtbot.addWidget(display)
    display.show()
    viewer = display.findChild(QWidget, "viewer")
    adopted = [child.objectName() for child in viewer._adopted_widgets]
    assert adopted == ["acquisition", "exposure", "centroid", "roi", "markers", "colormap", "las_settings"]
    assert viewer.findChild(QWidget, "acquisition").cam_prefix == "LAS:LHN:BAY1:CAM:02"


def test_btps_screens_have_no_typhos_commands():
    for path in (DEV_DIR / "screens" / "btps").glob("*.ui"):
        assert not re.search(r"<string>typhos ", path.read_text()), path


def test_grid_builds_from_snapshot(qtbot: QtBot):
    grid = LasIndicatorGrid()
    qtbot.addWidget(grid)
    grid.beamline = "LAS"
    cells = grid.findChildren(PVIndicatorCell)
    indicators = grid.findChildren(PVAlarmCircle)
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
    qtbot.addWidget(widget)
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
    circle.update_connection(True, "ca://A")
    circle.update_connection(True, "ca://B")
    circle.update_severity(0, "ca://A")
    circle.update_severity(0, "ca://B")
    assert circle.alarm_summary == AlarmLevel.NO_ALARM
    circle.update_severity(2, "ca://B")
    assert circle.alarm_summary == AlarmLevel.MAJOR
    assert "B: MAJOR" in circle.alarm_tooltip()
    circle.update_connection(False, "ca://A")
    assert circle.alarm_summary == AlarmLevel.DISCONNECTED
    assert "rgba(255,255,255,255)" in circle.styleSheet()


def test_open_device_prints_pydm_command():
    result = subprocess.run(
        [sys.executable, str(DEV_DIR / "open_device.py"), "--print", "las_bts_mcs2_01_m1"],
        capture_output=True,
        text=True,
        check=True,
        env={**__import__("os").environ, "PYTHONPATH": f"{DEV_DIR.parents[1]}:{DEV_DIR}"},
    )
    assert "smaract_detailed.ui" in result.stdout
    assert '"MOTOR": "LAS:BTS:MCS2:01:m1"' in result.stdout


def test_home_screen_imports_nothing_forbidden():
    """Load the full home screen in a fresh interpreter and check sys.modules."""
    script = (
        "import os, sys\n"
        "from pydm import PyDMApplication\n"
        "from pydm.display import load_file\n"
        "app = PyDMApplication(hide_nav_bar=True, hide_menu_bar=True, hide_status_bar=True)\n"
        # target=None loads in this process; the default (NEW_PROCESS) would spawn a separate pydm.
        f"display = load_file({str(DEV_DIR / 'las_home.py')!r}, target=None)\n"
        "assert len(display.grid.devices) == 44\n"
        "assert display.toolbar.tab.count() == 10\n"
        f"bad = sorted(m for m in sys.modules if m.split('.')[0] in {FORBIDDEN!r})\n"
        "print('FORBIDDEN', bad)\n"
        "sys.stdout.flush()\n"
        "os._exit(0)\n"
    )
    env = {
        **__import__("os").environ,
        "PYTHONPATH": f"{DEV_DIR.parents[1]}:{DEV_DIR}",
        "QT_QPA_PLATFORM": "offscreen",
        "LAS_DEVICE_DB": str(las_devices.CONFIG_DIR / "las_devices.yaml"),
    }
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env, timeout=120)
    assert "FORBIDDEN []" in result.stdout, result.stdout + result.stderr[-2000:]
