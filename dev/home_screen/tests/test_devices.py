"""devices.py and device_types.yaml: loading happi entries, happi kwargs, templates, and the device types."""

import json
from pathlib import Path

from conftest import LOCATIONS, PACKAGE_DIR, floorplan_config, snapshot
from home_screen.devices import DeviceInfo, _entry_to_info, find_device_type, load_device_types, load_devices


def test_json_database_filters_like_happi_search(tmp_path: Path):
    db = {
        "a": {"name": "a", "beamline": "LAS", "active": True, "device_class": "x.A", "location_group": "L"},
        "b": {"name": "b", "beamline": "LAS", "active": False, "device_class": "x.A"},
        "c": {"name": "c", "beamline": "TMO", "active": True, "device_class": "x.A"},
        "d": {"name": "d", "beamline": "las", "active": True, "device_class": "x.A", "prefix": None},
    }
    path = tmp_path / "db.json"
    path.write_text(json.dumps(db))
    devices = load_devices("LAS", path)
    assert [dev.name for dev in devices] == ["a", "d"]
    assert devices[1].prefix == ""


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


def test_templates_fill_macros_and_status_pvs():
    types = load_device_types()
    camera = DeviceInfo(name="cam", device_class="x.LasBasler", prefix="LAS:CAM:01:")
    dtype = types["pcdsdevices.areadetector.detectors.LasBasler"]
    assert dtype.macros_for(camera)["CAM"] == "LAS:CAM:01"
    assert "ca://LAS:CAM:01:DetectorState_RBV" in dtype.indicator_channels_for(camera)
    tip_tilt = DeviceInfo(
        name="mr1",
        device_class="pcdsdevices.epics_motor.SmarActTipTilt",
        prefix="LM1K4:OPA_MP1_MR1",
        kwargs={"tip_pv": "_TIP1", "tilt_pv": "_TILT1"},
    )
    dtype = types["pcdsdevices.epics_motor.SmarActTipTilt"]
    assert dtype.macros_for(tip_tilt)["TIP"] == "LM1K4:OPA_MP1_MR1_TIP1"
    assert "ca://LM1K4:OPA_MP1_MR1_TILT1.RBV" in dtype.indicator_channels_for(tip_tilt)
    elliptec = DeviceInfo(
        name="wp1", device_class="pcdsdevices.device_types.Ell9", prefix="LM1K4:EJX:ELL:1", kwargs={"channel": "3"}
    )
    dtype = types["pcdsdevices.device_types.Ell9"]
    assert dtype.macros_for(elliptec) == {"MOTOR": "LM1K4:EJX:ELL:1:M3", "NAME": "wp1", "STAGE": "ell9"}


def test_find_device_type_by_short_name():
    types = load_device_types()
    device = DeviceInfo(name="m", device_class="some.other.module.SmarAct")
    assert find_device_type(device, types) is types["pcdsdevices.epics_motor.SmarAct"]
    assert find_device_type(DeviceInfo(name="u", device_class="x.Unknown"), types) is None


def test_every_device_type_screen_is_in_the_package():
    types = load_device_types()
    assert types["pcdsdevices.epics_motor.SmarAct"].screen_path() == str(PACKAGE_DIR / "screens" / "smaract.py")
    # The BTPS opens through the LAS toolbar and has no status dot, so it has no device type
    assert "pcdsdevices.lasers.btps.BtpsState" not in types
    for dtype in types.values():
        assert dtype.indicator_pvs, dtype.device_class
        if dtype.screen_path():
            path = Path(dtype.screen_path())
            assert path.is_file() and path.is_relative_to(PACKAGE_DIR / "screens"), dtype.device_class


def test_every_location_has_a_snapshot():
    assert {location.name for location in LOCATIONS} >= {"las", "mods_ip1", "mods_ip2", "mods_qrix", "mods_crix"}
    for location in LOCATIONS:
        assert snapshot(location).is_file(), location.name


def test_device_types_cover_every_location(location: Path):
    """device_types.yaml is the one source of truth: every class active at every location has an entry."""
    types = load_device_types()
    devices = load_devices(floorplan_config(location)["beamline"], snapshot(location))
    assert devices, location.name
    missing = {
        dev.device_class
        for dev in devices
        if find_device_type(dev, types) is None and not dev.device_class.endswith("BtpsState")
    }
    assert not missing, missing
