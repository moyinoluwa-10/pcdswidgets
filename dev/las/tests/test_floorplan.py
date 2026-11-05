import os
import subprocess
import sys
from pathlib import Path

import floorplan
import pytest
from devices import DeviceType, _entry_to_info
from floorplan import FloorPlan, FloorPlanContext
from pydm.display import ScreenTarget, load_file
from pydm.widgets import PyDMEmbeddedDisplay
from pytestqt.qtbot import QtBot
from qtpy.QtCore import QEvent, QPoint, QRect, Qt
from qtpy.QtGui import QColor, QHelpEvent
from qtpy.QtWidgets import QWidget

from pcdswidgets.common.dock.tab_dock import TabDock

LAS_DIR = Path(__file__).resolve().parent.parent
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
    """Every active LAS happi device is in exactly one bay or area menu, except the BTPS (toolbar only)."""
    seen: list[str] = []
    for bay, cfg in context.config["bays"].items():
        seen.extend(leaf.device_name for opener in context.bay_openers(bay, cfg) for leaf in opener.leaves())
    for area in context.config["areas"].values():
        seen.extend(leaf.device_name for opener in context.resolve(area["opens"]) for leaf in opener.leaves())
    seen = [name for name in seen if name]
    assert sorted(seen) == sorted(dev.name for dev in context.devices if dev.name != "las_btps")


ALL_RACKS = [f"R{n:02d}" for n in range(1, 21)]
PDU_RACKS = ["R01", "R03", "R06", "R07", "R08", "R13", "R18"]


def test_hall_config_is_consistent(context: FloorPlanContext):
    """Column shares are sane, and every icon sits inside a known area."""
    hall = context.config["hall"]
    names = set()
    for column in hall["columns"]:
        if "racks" in column:
            names.update(r for group in column["racks"] for r in floorplan.rack_names(group["range"]))
        elif "bay" in column or "area" in column:
            names.add(column.get("bay") or column.get("area"))
            assert column["top"] + column["height"] <= 100, column
    assert {f"Bay {n}" for n in range(1, 5)} | {"BTS"} | set(ALL_RACKS) == names
    for icon in context.config["icons"]:
        assert icon["in"] in names, icon
        assert all(0 <= value <= 100 for value in icon["at"]), icon


def test_floor_plan_builds(plan: FloorPlan):
    names = [button.objectName() for button, _ in plan.areas]
    # Left to right: Bay 1, the R01-R10 column, Bay 2, BTS, Bay 3, the R11-R20 column, Bay 4
    assert names == ["Bay_1", *ALL_RACKS[:10], "Bay_2", "BTS", "Bay_3", *ALL_RACKS[10:], "Bay_4"]
    assert len(plan.icons) == 22
    clickable_racks = sorted(name for button, name in plan.areas if name.startswith("R") and button.openers)
    assert clickable_racks == PDU_RACKS


def test_racks_without_pdu_are_grey(plan: FloorPlan, context: FloorPlanContext):
    grey = QColor(context.config["hall"]["inactive"])
    for button, name in plan.areas:
        if name.startswith("R"):
            assert (button.color == grey) == (name not in PDU_RACKS), name
            assert (button.badge is not None) == (name in PDU_RACKS), name


def test_drawing_is_roughly_the_old_image(plan: FloorPlan):
    """At the old image size, areas land within a few pixels of where bg.png had them."""
    old_rects = {
        "Bay_1": QRect(47, 86, 163, 548),
        "Bay_3": QRect(851, 81, 156, 548),
        "BTS": QRect(550, 278, 261, 176),
        "R01": QRect(251, 37, 55, 55),
        "R19": QRect(1054, 521, 55, 55),
    }
    for button, _ in plan.areas:
        old = old_rects.get(button.objectName())
        if old is None:
            continue
        new = QRect(button.mapTo(plan, QPoint(0, 0)), button.size())
        for a, b in ((new.x(), old.x()), (new.y(), old.y()), (new.width(), old.width()), (new.height(), old.height())):
            assert abs(a - b) <= 15, (button.objectName(), new, old)


def test_icons_stay_inside_their_area(plan: FloorPlan):
    for button, (area_name, _, _) in plan.icons:
        area = plan.area(area_name)
        area_rect = QRect(area.mapTo(plan, QPoint(0, 0)), area.size())
        assert area_rect.contains(button.geometry().center()), (button.text(), area_name)


def test_new_toolbar_pdu_lights_up_its_rack(qtbot: QtBot, context: FloorPlanContext):
    """R05 has no PDU today; naming a toolbar button "... (R05)" is all it takes."""
    context.toolbar["PDUs"]["buttons"]["New PDU (R05)"] = {"type": "shell", "commands": ["echo r05"]}
    dock = TabDock()
    qtbot.addWidget(dock)
    widget = FloorPlan(context)
    qtbot.addWidget(widget)
    r05 = widget.area("R05")
    assert r05.single().command == ["echo r05"]
    assert r05.color != QColor(context.config["hall"]["inactive"])


def test_bay_menu_lists_controls(plan: FloorPlan):
    bay3 = next(button for button, _ in plan.areas if button.objectName() == "Bay_3")
    assert bay3.single() is None
    menu = bay3.build_menu()
    titles = [action.text() for action in menu.actions() if action.text()]
    assert titles == ["Bay 3", "Cameras", "SmarAct Motors", "Temperature / Humidity", "Shutters", "Tools"]


def test_rack_click_runs_its_pdu_toolbar_button(plan: FloorPlan, no_external_commands):
    """R07 runs the toolbar's "Zone 1 TiSaph PSU/Chiller PDU (R07)" EDM launcher."""
    rack = next(button for button, _ in plan.areas if button.objectName() == "R07")
    target = rack.single()
    assert target.title == "Zone 1 TiSaph PSU/Chiller PDU (R07)"
    rack.handle_click(Qt.LeftButton, QPoint(0, 0))
    assert no_external_commands == [
        "/reg/g/pcds/epics-dev/rnazir/ioc/las/ioc-las-pdu_snmp/build/iocBoot/ioc-las-lhn-pwr-07/edm-ioc-las-lhn-pwr-07.cmd"
    ]


def test_racks_follow_toolbar_labels(context: FloorPlanContext):
    """Every "(Rxx)" PDU button in the toolbar lands on its rack, and nothing else does."""
    labelled = {}
    for name in context.toolbar["PDUs"]["buttons"]:
        match = floorplan.RACK_IN_NAME.search(name)
        if match:
            labelled.setdefault(match.group(1), []).append(name)
    for rack in ALL_RACKS:
        titles = [opener.title for opener in context.rack_openers(rack, {})]
        assert titles == labelled.get(rack, []), rack


def test_rack_opens_override(context: FloorPlanContext):
    openers = context.rack_openers("R02", {"opens": [{"device": "las_lhn_bay1_env_sens_1"}]})
    assert [opener.device_name for opener in openers] == ["las_lhn_bay1_env_sens_1"]


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


def test_qpcs_button_is_a_submenu_not_five_windows(plan: FloorPlan, no_external_commands):
    """ "BTS QPCs" has a command per title (las-pci-01..05): one menu entry each, not all at once."""
    bts = next(button for button, _ in plan.areas if button.objectName() == "BTS")
    qpcs = next(opener for opener in bts.openers if opener.title == "BTS QPCs")
    assert [child.title for child in qpcs.children] == [f"las-pci-0{n}" for n in range(1, 6)]
    assert all(len(child.command) == 1 for child in qpcs.children)
    floorplan.run_command(qpcs.children[1].command)
    assert len(no_external_commands) == 1 and "pci-02" in no_external_commands[0]


def test_toolbar_entry_can_pick_one_title(context: FloorPlanContext):
    one = context.toolbar_opener("NEH Beam Transport", "BTS QPCs", "las-pci-03")
    assert one.title == "las-pci-03" and len(one.command) == 1 and "pci-03" in one.command[0]
    assert "(missing)" in context.toolbar_opener("NEH Beam Transport", "BTS QPCs", "nope").title


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
    dtype = DeviceType(device_class=entry["device_class"], indicator_pvs=["{prefix}{tip_pv}:STEP_COUNT"])
    assert dtype.indicator_channels_for(info) == ["ca://LAS:X_TIP1:STEP_COUNT"]


def test_status_dots_watch_device_pvs(plan: FloorPlan):
    icon = next(button for button, _ in plan.icons if button.text() == "SmarAct")
    assert set(icon.status._pv_channels) == {
        "ca://LAS:BTS:MCS2:01:m1.RBV",
        "ca://LAS:BTS:MCS2:01:m2.RBV",
        "ca://LAS:BTS:MCS2:01:m3.RBV",
    }


def test_icon_tooltip_lists_bad_pvs(plan: FloorPlan, monkeypatch: pytest.MonkeyPatch):
    icon = next(button for button, _ in plan.icons if button.text() == "SmarAct")
    shown = []
    monkeypatch.setattr(floorplan.QToolTip, "showText", lambda pos, text, widget: shown.append(text))
    tooltip_event = QHelpEvent(QEvent.ToolTip, QPoint(5, 5), icon.mapToGlobal(QPoint(5, 5)))
    # Nothing connects in the tests, so every PV is disconnected
    assert icon.event(tooltip_event)
    assert shown[-1].startswith(icon.toolTip())
    assert "3 of 3 PVs not OK" in shown[-1]
    assert "LAS:BTS:MCS2:01:m1.RBV: DISCONNECTED" in shown[-1]
    # All fine: the icon's normal tooltip only
    for address in icon.status._pv_channels:
        icon.status.update_connection(True, addr=address)
        icon.status.update_severity(0, addr=address)
    assert icon.status.alarm_tooltip() == ""
    count = len(shown)
    icon.event(tooltip_event)
    assert len(shown) == count


def test_icons_shrink_with_the_image(plan: FloorPlan):
    plan.resize(678, 336)
    icon, _ = plan.icons[0]
    assert icon.toolButtonStyle() == Qt.ToolButtonIconOnly
    plan.resize(1356, 672)
    assert icon.toolButtonStyle() == Qt.ToolButtonTextUnderIcon


def test_device_types_point_at_local_screens():
    """Every configured screen is in this directory and exists."""
    types = floorplan.load_device_types()
    assert types["pcdsdevices.epics_motor.SmarAct"].screen_path() == str(LAS_DIR / "screens" / "smaract.py")
    assert types["pcdsdevices.epics_motor.SmarAct"].indicator_pvs == ["{prefix}.RBV"]
    # The BTPS opens through the toolbar and has no status dot, so it has no device type
    assert "pcdsdevices.lasers.btps.BtpsState" not in types
    for dtype in types.values():
        if dtype.screen_path():
            assert Path(dtype.screen_path()).is_file(), dtype.device_class
            assert Path(dtype.screen_path()).is_relative_to(LAS_DIR), dtype.device_class


def test_btps_runs_toolbar_command(plan: FloorPlan, no_external_commands):
    """BTPS opens the toolbar's "BTPS Overview" (run_btps.sh) externally, with no status dot."""
    icon = next(button for button, _ in plan.icons if button.text() == "BTPS")
    target = icon.single()
    assert target.command == ["/cds/group/pcds/epics-dev/screens/pydm/las/bts/run_btps.sh"]
    assert not target.dockable
    assert icon.status is None
    icon.handle_click(Qt.LeftButton, QPoint(0, 0))
    assert no_external_commands == target.command
    # The BTS menu has one BTPS entry, the same command
    bts = next(button for button, _ in plan.areas if button.objectName() == "BTS")
    btps_entries = [opener for opener in bts.openers if "BTPS" in opener.title]
    assert [opener.command for opener in btps_entries] == [target.command]


def test_smaract_screen_has_expert_and_advanced_panels(qtbot: QtBot):
    display = load_file(
        str(LAS_DIR / "screens" / "smaract.py"),
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
        ("smaract.py", {"MOTOR": "LAS:BTS:MCS2:01:m1", "NAME": "m1"}),
        ("las_basler.ui", {"CAM": "LAS:LHN:BAY1:CAM:01", "NAME": "cam", "DESC": "Bay 1 cam"}),
        ("las_basler_settings.ui", {"CAM": "LAS:LHN:BAY1:CAM:01"}),
    ],
)
def test_screens_load(qtbot: QtBot, screen: str, macros: dict[str, str]):
    display = load_file(str(LAS_DIR / "screens" / screen), macros=macros, target=ScreenTarget.DIALOG)
    qtbot.addWidget(display)
    # Embedded displays load lazily; force them so their macros are checked too
    embedded = display.findChildren(PyDMEmbeddedDisplay)
    for child in embedded:
        child.load_if_needed()
        assert child.embedded_widget is not None, child.filename
    addresses = channel_addresses(display)
    assert addresses
    assert not [addr for addr in addresses if "${" in addr]
    if screen == "las_basler.ui":
        assert [child.objectName() for child in embedded] == ["las_settings"]
        assert "ca://LAS:LHN:BAY1:CAM:01:RESET.PROC" in addresses


def test_minimum_height_fits_toolbar_and_floor_plan(qtbot: QtBot):
    """At the smallest window size, no toolbar tab scrolls and the floor plan keeps its minimum."""
    home = load_file(str(LAS_DIR / "las_home.py"), target=None)
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
        f"display = load_file({str(LAS_DIR / 'las_home.py')!r}, target=None)\n"
        "assert len(display.floorplan.icons) == 22\n"
        "assert display.toolbar.tab.count() == 10\n"
        f"bad = sorted(m for m in sys.modules if m.split('.')[0] in {FORBIDDEN!r})\n"
        "print('FORBIDDEN', bad)\n"
        f"dev_dir, las_dir = {str(LAS_DIR.parent) + os.sep!r}, {str(LAS_DIR) + os.sep!r}\n"
        "files = [getattr(mod, '__file__', '') or '' for mod in list(sys.modules.values())]\n"
        "outside = sorted(f for f in files if f.startswith(dev_dir) and not f.startswith(las_dir))\n"
        "print('OUTSIDE', outside)\n"
        "sys.stdout.flush()\n"
        "os._exit(0)\n"
    )
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(filter(None, [str(LAS_DIR), os.environ.get("PYTHONPATH", "")])),
        "QT_QPA_PLATFORM": "offscreen",
    }
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env, timeout=120)
    assert "FORBIDDEN []" in result.stdout, result.stdout + result.stderr[-2000:]
    assert "OUTSIDE []" in result.stdout, result.stdout
