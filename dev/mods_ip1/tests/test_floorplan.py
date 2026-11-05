import os
import subprocess
import sys
from pathlib import Path

import floorplan
import pytest
from devices import DeviceInfo, _entry_to_info
from floorplan import FloorPlan, FloorPlanContext
from pydm.display import ScreenTarget, load_file
from pydm.widgets import PyDMEmbeddedDisplay
from pytestqt.qtbot import QtBot
from qtpy.QtCore import QEvent, QPoint, QRect, Qt
from qtpy.QtGui import QHelpEvent
from qtpy.QtWidgets import QLabel, QScrollArea, QWidget

from pcdswidgets.common.dock.tab_dock import TabDock

APP_DIR = Path(__file__).resolve().parent.parent
FORBIDDEN = ("happi", "ophyd", "pcdsdevices", "typhos", "lucid")
STATIONS = ["INJ", "COM", "OPA", "HRM", "ATM", "EJX"]
NF_FF = "/cds/group/pcds/epics-dev/screens/pydm/las/mods_ip1/launch_nf_ff_alignment.sh"


@pytest.fixture
def context(qapp) -> FloorPlanContext:
    # Building icons needs a QApplication
    return FloorPlanContext()


@pytest.fixture
def plan(qtbot: QtBot, context: FloorPlanContext) -> FloorPlan:
    dock = TabDock()
    qtbot.addWidget(dock)
    dock.show()
    widget = FloorPlan(context)
    qtbot.addWidget(widget)
    widget.resize(1000, 526)
    widget.show()
    return widget


def channel_addresses(widget: QWidget) -> set[str]:
    addresses = set()
    for child in [widget, *widget.findChildren(QWidget)]:
        channels = getattr(child, "channels", None)
        if callable(channels):
            addresses.update(ch.address for ch in channels() or [] if getattr(ch, "address", None))
    return addresses


def icon_in(plan: FloorPlan, station: str, label: str) -> floorplan.IconButton:
    return next(button for button, (area, _, _) in plan.icons if area == station and button.text() == label)


def test_config_references_resolve(context: FloorPlanContext):
    config = context.config
    for icon in config["icons"]:
        openers = context.resolve(icon["opens"])
        assert openers, icon
        assert all("(missing)" not in leaf.title for opener in openers for leaf in opener.leaves()), icon
    for station, cfg in config["stations"].items():
        leaves = [leaf for opener in context.station_openers(station, cfg) for leaf in opener.leaves()]
        assert leaves, station
        assert all("(missing)" not in leaf.title for leaf in leaves), station


def test_every_device_is_reachable(context: FloorPlanContext):
    """Every active IP1_MODS happi device is in exactly one station menu."""
    seen = [
        leaf.device_name
        for station, cfg in context.config["stations"].items()
        for opener in context.station_openers(station, cfg)
        for leaf in opener.leaves()
        if leaf.device_name
    ]
    assert len(context.devices) == 59
    assert sorted(seen) == sorted(dev.name for dev in context.devices)


def test_every_icon_has_something_to_open(context: FloorPlanContext):
    """Icons only exist for functions a station actually has active devices for."""
    for icon in context.config["icons"]:
        leaves = [leaf for opener in context.resolve(icon["opens"]) for leaf in opener.leaves()]
        assert leaves and all(leaf.dockable or leaf.command for leaf in leaves), icon


def test_hall_config_is_consistent(context: FloorPlanContext):
    """Stations are in beam order, fit vertically, and every icon sits inside one."""
    columns = context.config["hall"]["columns"]
    assert [column["station"] for column in columns if "station" in column] == STATIONS
    for column in columns:
        if "station" in column:
            assert column["top"] + column["height"] <= 100, column
    for icon in context.config["icons"]:
        assert icon["in"] in STATIONS, icon
        assert all(0 <= value <= 100 for value in icon["at"]), icon


def test_floor_plan_builds(plan: FloorPlan):
    assert [name for _, name in plan.areas] == STATIONS
    assert len(plan.icons) == 24
    assert all(button.openers for button, _ in plan.areas)


def test_icons_stay_inside_their_station(plan: FloorPlan):
    for button, (area_name, _, _) in plan.icons:
        area = plan.area(area_name)
        area_rect = QRect(area.mapTo(plan, QPoint(0, 0)), area.size())
        assert area_rect.contains(button.geometry()), (button.text(), area_name)


def test_icons_do_not_overlap(plan: FloorPlan):
    rects = [(button.text(), area, button.geometry()) for button, (area, _, _) in plan.icons]
    for index, (label, area, rect) in enumerate(rects):
        for other_label, other_area, other in rects[index + 1 :]:
            assert not rect.intersects(other), (area, label, other_area, other_label)


def test_station_menu_lists_controls(plan: FloorPlan):
    ejx = plan.area("EJX")
    assert ejx.single() is None
    titles = [action.text() for action in ejx.build_menu().actions() if action.text()]
    assert titles == [
        "EJX",
        "Cameras",
        "SmarAct Motors",
        "Spectrometers",
        "Elliptecs",
        "Power Meters",
        "Temperature / Humidity",
        "Tools",
    ]


def test_toolbar_button_with_several_commands(context: FloorPlanContext):
    """nf-ff-alignment has a command per title: pick one by title, or get one opener per command."""
    com = context.toolbar_opener("Tools", "nf-ff-alignment", "COM_DP1")
    assert com.title == "COM_DP1"
    assert com.command == [f"{NF_FF} lm1k4_com_dp1.toml"]
    both = context.toolbar_opener("Tools", "nf-ff-alignment")
    assert [(child.title, child.command) for child in both.children] == [
        ("COM_DP1", [f"{NF_FF} lm1k4_com_dp1.toml"]),
        ("ATM_DP1", [f"{NF_FF} lm1k4_atm_dp1.toml"]),
    ]
    assert "(missing)" in context.toolbar_opener("Tools", "nf-ff-alignment", "NOPE").title


def test_station_tools_run_externally(plan: FloorPlan, no_external_commands):
    tools = next(opener for opener in plan.area("ATM").openers if opener.title == "Tools")
    assert [child.title for child in tools.children] == ["ATM_DP1", "ATM non-LSS Shutter"]
    floorplan.run_command(tools.children[0].command)
    assert no_external_commands == [f"{NF_FF} lm1k4_atm_dp1.toml"]


def test_shutter_icon_runs_toolbar_command(plan: FloorPlan, no_external_commands):
    icon = icon_in(plan, "EJX", "Shutter")
    assert icon.status is None
    icon.handle_click(Qt.LeftButton, QPoint(0, 0))
    assert no_external_commands == [
        "/cds/home/a/aberges/trunk/screens/tmo_mods_shutter/launchgui_lm1k4_ejx_shutter.cmd"
    ]


def test_icon_click_opens_device(plan: FloorPlan):
    icon_in(plan, "INJ", "T/H").handle_click(Qt.LeftButton, QPoint(0, 0))
    tabs = TabDock.get_instance().get_open_tab_widget()
    assert tabs.tabText(tabs.currentIndex()) == "lm1k4_inj_env_sens"


def test_status_dots_fill_in_happi_kwargs(plan: FloorPlan):
    """Tip/tilt and Elliptec PVs come from per-device happi kwargs (tip_pv, channel), filled in from the entry."""
    opa = icon_in(plan, "OPA", "SmarAct").status._pv_channels
    assert "ca://LM1K4:OPA_MP1_MR1_LM1.RBV" in opa
    assert "ca://LM1K4:OPA_MP1_MR1_TIP1:STEP_COUNT" in opa
    assert "ca://LM1K4:OPA_MP1_MR4_TILT1:STEP_COUNT" in opa
    ejx = icon_in(plan, "EJX", "Elliptecs").status._pv_channels
    assert "ca://LM1K4:EJX:ELL:2:M1:CURPOS" in ejx
    every = [address for button, _ in plan.icons if button.status for address in button.status._pv_channels]
    assert not [address for address in every if "{" in address]


def test_happi_kwargs_are_filled_in_from_the_entry():
    entry = {
        "name": "tt",
        "device_class": "pcdsdevices.epics_motor.SmarActTipTilt",
        "prefix": "LM1K4:X",
        "ioc_tip_suffix": "_TIP1",
        "kwargs": {"name": "{{name}}", "tip_pv": "{{ioc_tip_suffix}}", "port": "15"},
    }
    info = _entry_to_info(entry)
    assert info.kwargs == {"tip_pv": "_TIP1", "port": "15"}
    assert info.template_values()["tip_pv"] == "_TIP1"


def test_devices_without_a_screen_open_a_placeholder(context: FloorPlanContext, qtbot: QtBot):
    device = context.devices_by_name["lm1k4_opa_mp1_mr1"]
    display = context.screens.display_for_device(device)
    qtbot.addWidget(display)
    text = display.findChild(QLabel).text()
    assert "SmarActTipTilt" in text and "no screen" in text
    assert isinstance(device, DeviceInfo)


def test_spectrometers_open_the_qmini_screen(context: FloorPlanContext, qtbot: QtBot):
    device = context.devices_by_name["lm1k4_ejx_dp1_sp1"]
    display = context.screens.display_for_device(device)
    qtbot.addWidget(display)
    assert type(display).__name__ == "QminiScreen"
    assert display.windowTitle() == "lm1k4_ejx_dp1_sp1"
    assert "ca://LM1K4:EJX_DP1_SP1:SPECTRUM" in [curve.y_address for curve in display.qmini.ui.plot._curves]
    # In a dock shorter than the screen's minimum it scrolls instead of squashing
    display.show()
    display.resize(600, 300)
    qtbot.wait(10)
    assert display.qmini.height() >= display.qmini.minimumSizeHint().height()
    assert display.findChild(QScrollArea).verticalScrollBar().maximum() > 0


def test_icon_tooltip_lists_bad_pvs(plan: FloorPlan, monkeypatch: pytest.MonkeyPatch):
    icon = icon_in(plan, "INJ", "Cameras")
    shown = []
    monkeypatch.setattr(floorplan.QToolTip, "showText", lambda pos, text, widget: shown.append(text))
    tooltip_event = QHelpEvent(QEvent.ToolTip, QPoint(5, 5), icon.mapToGlobal(QPoint(5, 5)))
    # Nothing connects in the tests, so every PV is disconnected
    assert icon.event(tooltip_event)
    assert shown[-1].startswith(icon.toolTip())
    assert "20 of 20 PVs not OK" in shown[-1]
    for address in icon.status._pv_channels:
        icon.status.update_connection(True, addr=address)
        icon.status.update_severity(0, addr=address)
    assert icon.status.alarm_tooltip() == ""


def test_icons_shrink_with_the_drawing(plan: FloorPlan):
    plan.resize(500, 263)
    icon, _ = plan.icons[0]
    assert icon.toolButtonStyle() == Qt.ToolButtonIconOnly
    plan.resize(1000, 526)
    assert icon.toolButtonStyle() == Qt.ToolButtonTextUnderIcon


def test_device_types_point_at_local_screens():
    """Every configured screen is in this directory and exists."""
    types = floorplan.load_device_types()
    assert types["pcdsdevices.epics_motor.SmarAct"].screen_path() == str(APP_DIR / "screens" / "smaract.py")
    for dtype in types.values():
        assert dtype.indicator_pvs, dtype.device_class
        if dtype.screen_path():
            assert Path(dtype.screen_path()).is_file(), dtype.device_class
            assert Path(dtype.screen_path()).is_relative_to(APP_DIR), dtype.device_class


def test_every_active_class_has_a_device_type(context: FloorPlanContext):
    missing = {dev.device_class for dev in context.devices if floorplan.find_device_type(dev, context.types) is None}
    assert not missing


@pytest.mark.parametrize(
    "screen,macros",
    [
        ("smaract.py", {"MOTOR": "LM1K4:INJ_MP2_LS2", "NAME": "lm1k4_inj_mp2_ls2"}),
        ("las_basler.ui", {"CAM": "LM1K4:INJ_DP1_TF1_NF1", "NAME": "cam", "DESC": "INJ NF"}),
        ("las_basler_settings.ui", {"CAM": "LM1K4:INJ_DP1_TF1_NF1"}),
        ("env_monitor.ui", {"PREFIX": "LM1K4:INJ_BHC_AI_01", "NAME": "lm1k4_inj_env_sens"}),
        ("qmini.py", {"prefix": "LM1K4:EJX_DP1_SP1", "NAME": "lm1k4_ejx_dp1_sp1"}),
    ],
)
def test_screens_load(qtbot: QtBot, screen: str, macros: dict[str, str]):
    display = load_file(str(APP_DIR / "screens" / screen), macros=macros, target=ScreenTarget.DIALOG)
    qtbot.addWidget(display)
    # Embedded displays load lazily; force them so their macros are checked too
    for child in display.findChildren(PyDMEmbeddedDisplay):
        child.load_if_needed()
        assert child.embedded_widget is not None, child.filename
    addresses = channel_addresses(display)
    assert addresses
    assert not [addr for addr in addresses if "${" in addr]


def test_minimum_height_fits_toolbar_and_floor_plan(qtbot: QtBot):
    """At the smallest window size, no toolbar tab scrolls and the floor plan keeps its minimum."""
    home = load_file(str(APP_DIR / "mods_ip1_home.py"), target=None)
    qtbot.addWidget(home)
    home.show()
    home.resize(home.minimumSizeHint())
    qtbot.wait(50)
    tabs = home.toolbar.tab
    for index in range(tabs.count()):
        tabs.setCurrentIndex(index)
        qtbot.wait(10)
        assert tabs.widget(index).verticalScrollBar().maximum() == 0, tabs.tabText(index)
    assert home.floorplan.height() >= home.floorplan.minimumSizeHint().height()


def test_home_screen_imports_nothing_forbidden():
    """Load the full home screen in a fresh interpreter: nothing forbidden, nothing from the rest of dev/."""
    script = (
        "import os, sys\n"
        "from pydm import PyDMApplication\n"
        "from pydm.display import load_file\n"
        "app = PyDMApplication(hide_nav_bar=True, hide_menu_bar=True, hide_status_bar=True)\n"
        # target=None loads in this process; the default (NEW_PROCESS) would spawn a separate pydm.
        f"display = load_file({str(APP_DIR / 'mods_ip1_home.py')!r}, target=None)\n"
        "assert len(display.floorplan.icons) == 24\n"
        "assert display.toolbar.tab.count() == 4\n"
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
