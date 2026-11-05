import os
import subprocess
import sys
from pathlib import Path

import floorplan
import pytest
from floorplan import FloorPlan, FloorPlanContext
from pydm.display import ScreenTarget, load_file
from pytestqt.qtbot import QtBot
from qtpy.QtCore import QPoint, QRect, Qt
from qtpy.QtWidgets import QWidget

from pcdswidgets.common.dock.tab_dock import TabDock

V2_DIR = Path(__file__).resolve().parent.parent
FORBIDDEN = ("happi", "ophyd", "pcdsdevices", "typhos", "lucid")


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
    widget.resize(1356, 672)
    widget.show()
    return widget


def channel_addresses(widget: QWidget) -> set[str]:
    addresses = set()
    for child in [widget, *widget.findChildren(QWidget)]:
        channels = getattr(child, "channels", None)
        if callable(channels):
            addresses.update(ch.address for ch in channels() or [] if getattr(ch, "address", None))
    return addresses


def test_config_references_resolve(context: FloorPlanContext):
    config = context.config
    for icon in config["icons"]:
        openers = context.resolve(icon["opens"])
        assert openers, icon
        assert all("(missing)" not in leaf.title for opener in openers for leaf in opener.leaves()), icon
    for name, area in config["areas"].items():
        assert context.resolve(area["opens"]), name
        assert all("(missing)" not in o.title for o in context.resolve(area["opens"]))
    for bay, cfg in config["bays"].items():
        leaves = [leaf for opener in context.bay_openers(bay, cfg) for leaf in opener.leaves()]
        assert leaves, bay
        assert all("(missing)" not in leaf.title for leaf in leaves), bay


def test_every_las_device_is_reachable(context: FloorPlanContext):
    """Every active LAS happi device is in exactly one bay or area menu."""
    seen: list[str] = []
    for bay, cfg in context.config["bays"].items():
        seen.extend(leaf.device_name for opener in context.bay_openers(bay, cfg) for leaf in opener.leaves())
    for area in context.config["areas"].values():
        seen.extend(leaf.device_name for opener in context.resolve(area["opens"]) for leaf in opener.leaves())
    seen = [name for name in seen if name]
    assert sorted(seen) == sorted(dev.name for dev in context.devices)


def test_layout_is_inside_the_image(context: FloorPlanContext):
    image = QRect(0, 0, 1356, 672)
    config = context.config
    for group in ("bays", "areas", "racks"):
        for name, cfg in config[group].items():
            assert image.contains(QRect(*cfg["rect"])), name
    for icon in config["icons"]:
        assert image.contains(QPoint(*icon["pos"])), icon


def test_floor_plan_builds(plan: FloorPlan):
    names = [button.objectName() for button, _ in plan.areas]
    assert names[:5] == ["Bay_1", "Bay_2", "Bay_3", "Bay_4", "BTS"]
    assert len(plan.icons) == 22
    clickable_racks = sorted(
        button.objectName() for button, _ in plan.areas if button.objectName().startswith("R") and button.openers
    )
    assert clickable_racks == ["R01", "R03", "R06", "R07", "R08", "R13", "R18"]


def test_full_size_geometry_matches_config(plan: FloorPlan):
    for button, rect in plan.areas:
        assert button.geometry() == rect, button.objectName()


def test_bay_menu_lists_controls(plan: FloorPlan):
    bay3 = next(button for button, _ in plan.areas if button.objectName() == "Bay_3")
    assert bay3.single() is None
    menu = bay3.build_menu()
    titles = [action.text() for action in menu.actions() if action.text()]
    assert titles == ["Bay 3", "Cameras", "SmarAct Motors", "Temperature / Humidity", "Shutters", "Tools"]


def test_rack_click_opens_pdu_in_dock(plan: FloorPlan):
    rack = next(button for button, _ in plan.areas if button.objectName() == "R07")
    rack.handle_click(Qt.LeftButton, QPoint(0, 0))
    tabs = TabDock.get_instance().get_open_tab_widget()
    assert tabs.tabText(tabs.currentIndex()) == "R07 PDU"
    widget = tabs.currentWidget()
    assert "ca://LAS:LHN:PWR:07:Outlet:24:setPduOutletCommand" in channel_addresses(widget)


def test_icon_click_opens_device(plan: FloorPlan):
    icon = next(button for button, _ in plan.icons if button.text() == "T/H")
    icon.handle_click(Qt.LeftButton, QPoint(0, 0))
    tabs = TabDock.get_instance().get_open_tab_widget()
    assert tabs.tabText(tabs.currentIndex()) == "las_lhn_bay1_env_sens_1"


def test_toolbar_entries_run_externally(plan: FloorPlan, no_external_commands):
    bts = next(button for button, _ in plan.areas if button.objectName() == "BTS")
    btms = next(opener for opener in bts.openers if opener.title == "BTMS Overview")
    assert btms.command == ["/cds/group/pcds/epics-dev/screens/pydm/las/bts/run_btms.sh"]
    floorplan.run_command(btms.command)
    assert no_external_commands == btms.command


def test_status_dots_watch_device_pvs(plan: FloorPlan):
    icon = next(button for button, _ in plan.icons if button.text() == "SmarAct")
    assert set(icon.status._pv_channels) == {
        "ca://LAS:BTS:MCS2:01:m1.RBV",
        "ca://LAS:BTS:MCS2:01:m2.RBV",
        "ca://LAS:BTS:MCS2:01:m3.RBV",
    }


def test_icons_shrink_with_the_image(plan: FloorPlan):
    plan.resize(678, 336)
    icon, _ = plan.icons[0]
    assert icon.toolButtonStyle() == Qt.ToolButtonIconOnly
    plan.resize(1356, 672)
    assert icon.toolButtonStyle() == Qt.ToolButtonTextUnderIcon


def test_smaract_override_is_v2_only():
    from las_devices import load_device_types

    smaract = "pcdsdevices.epics_motor.SmarAct"
    v2 = floorplan.load_v2_device_types()[smaract]
    v1 = load_device_types()[smaract]
    assert v2.screen_path() == str(V2_DIR / "screens" / "smaract_r4.py")
    assert v1.screen_path().endswith("v1/screens/smaract_detailed.ui")
    # indicator PVs come from v1 when the override leaves them out
    assert v2.indicator_pvs == v1.indicator_pvs == ["{prefix}.RBV"]


def test_btps_runs_toolbar_command_and_keeps_status(plan: FloorPlan, no_external_commands):
    """BTPS opens the toolbar's "BTPS Overview" (run_btps.sh) externally, with las_btps's status PVs."""
    icon = next(button for button, _ in plan.icons if button.text() == "BTPS")
    target = icon.single()
    assert target.command == ["/cds/group/pcds/epics-dev/screens/pydm/las/bts/run_btps.sh"]
    assert not target.dockable
    assert len(icon.status._pv_channels) == 732
    icon.handle_click(Qt.LeftButton, QPoint(0, 0))
    assert no_external_commands == target.command
    # The BTS menu has one BTPS entry, the same command
    bts = next(button for button, _ in plan.areas if button.objectName() == "BTS")
    btps_entries = [opener for opener in bts.openers if "BTPS" in opener.title]
    assert [opener.command for opener in btps_entries] == [target.command]
    assert "pcdsdevices.lasers.btps.BtpsState" not in floorplan.load_device_types(floorplan.DEVICE_TYPES_FILE)


def test_smaract_screen_has_expert_and_advanced_panels(qtbot: QtBot):
    display = load_file(
        str(V2_DIR / "screens" / "smaract_r4.py"),
        macros={"MOTOR": "LAS:BTS:MCS2:01:m1", "NAME": "las_bts_mcs2_01_m1"},
        target=ScreenTarget.DIALOG,
    )
    qtbot.addWidget(display)
    tabs = display.advanced.tabWidget
    assert [tabs.tabText(i) for i in range(tabs.count())] == [
        "Open-loop",
        "Closed-loop",
        "Diagnostics",
        "Configuration",
    ]
    addresses = channel_addresses(display)
    assert "ca://LAS:BTS:MCS2:01:m1:STATE_RBV" in addresses
    assert display.windowTitle() == "las_bts_mcs2_01_m1"


@pytest.mark.parametrize(
    "screen,macros",
    [
        ("laser_shutter.ui", {"LS": "LS1", "TITLE": "LS1 (Bay 1)"}),
        ("pdu_tripplite.py", {"PRE": "LAS:LHN:PWR:07", "TITLE": "R07", "N_CHAN": "24"}),
        ("smaract_r4.py", {"MOTOR": "LAS:BTS:MCS2:01:m1", "NAME": "m1"}),
    ],
)
def test_v2_screens_load(qtbot: QtBot, screen: str, macros: dict[str, str]):
    display = load_file(str(V2_DIR / "screens" / screen), macros=macros, target=ScreenTarget.DIALOG)
    qtbot.addWidget(display)
    addresses = channel_addresses(display)
    assert addresses
    assert not [addr for addr in addresses if "${" in addr]


def test_minimum_height_fits_toolbar_and_floor_plan(qtbot: QtBot):
    """At the smallest window size, no toolbar tab scrolls and the floor plan keeps its minimum."""
    home = load_file(str(V2_DIR / "las_home.py"), target=None)
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
    """Load the full v2 home screen in a fresh interpreter and check sys.modules."""
    script = (
        "import os, sys\n"
        "from pydm import PyDMApplication\n"
        "from pydm.display import load_file\n"
        "app = PyDMApplication(hide_nav_bar=True, hide_menu_bar=True, hide_status_bar=True)\n"
        # target=None loads in this process; the default (NEW_PROCESS) would spawn a separate pydm.
        f"display = load_file({str(V2_DIR / 'las_home.py')!r}, target=None)\n"
        "assert len(display.floorplan.icons) == 22\n"
        "assert display.toolbar.tab.count() == 10\n"
        f"bad = sorted(m for m in sys.modules if m.split('.')[0] in {FORBIDDEN!r})\n"
        "print('FORBIDDEN', bad)\n"
        "sys.stdout.flush()\n"
        "os._exit(0)\n"
    )
    env = {
        **os.environ,
        "PYTHONPATH": f"{V2_DIR.parents[1]}:{V2_DIR}:{V2_DIR.parent / 'v1'}",
        "QT_QPA_PLATFORM": "offscreen",
    }
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env, timeout=120)
    assert "FORBIDDEN []" in result.stdout, result.stdout + result.stderr[-2000:]
