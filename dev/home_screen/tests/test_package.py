"""
The shared package on its own, and against every location that uses it (each dev/<location> with a
config/floorplan.yaml). Each location's own tests (dev/<location>/tests) check its config and devices.
"""

import json
from pathlib import Path

import pytest
import yaml
from devices import find_device_type, load_device_types, load_devices
from floorplan import FloorPlanContext

PACKAGE_DIR = Path(__file__).resolve().parent.parent
LOCATIONS = sorted(path.parent.parent for path in PACKAGE_DIR.parent.glob("*/config/floorplan.yaml"))


def test_the_known_locations_use_the_package():
    assert {location.name for location in LOCATIONS} >= {"las", "mods_ip1", "mods_ip2", "mods_qrix", "mods_crix"}


def test_every_device_type_screen_is_in_the_package():
    for dtype in load_device_types().values():
        if dtype.screen_path():
            path = Path(dtype.screen_path())
            assert path.is_file() and path.is_relative_to(PACKAGE_DIR / "screens"), dtype.device_class
        assert dtype.indicator_pvs, dtype.device_class


@pytest.mark.parametrize("location", LOCATIONS, ids=lambda path: path.name)
def test_location_config_names_beamline_title_and_toolbar(location: Path):
    config = yaml.safe_load((location / "config" / "floorplan.yaml").read_text())
    assert config["beamline"] and config["title"], location.name
    assert (location / "config" / config["toolbar"]).is_file(), location.name


@pytest.mark.parametrize("location", LOCATIONS, ids=lambda path: path.name)
def test_device_types_cover_every_location(location: Path):
    """device_types.yaml is the one source of truth: every class active at every location has an entry."""
    snapshot = location / "tests" / "devices_snapshot.yaml"
    if not snapshot.is_file():
        pytest.skip(f"{location.name} has no device snapshot")
    config = yaml.safe_load((location / "config" / "floorplan.yaml").read_text())
    types = load_device_types()
    missing = {
        dev.device_class
        for dev in load_devices(config["beamline"], snapshot)
        if find_device_type(dev, types) is None and not dev.device_class.endswith("BtpsState")
    }
    assert not missing, (location.name, missing)


def test_context_needs_a_floorplan(monkeypatch):
    monkeypatch.delenv("HOME_FLOORPLAN", raising=False)
    with pytest.raises(RuntimeError, match="HOME_FLOORPLAN"):
        FloorPlanContext()


@pytest.mark.parametrize("location", LOCATIONS, ids=lambda path: path.name)
def test_context_loads_its_beamline_from_a_happi_database(location: Path, tmp_path: Path, qapp):
    """With a happi JSON database (what the launchers use), only the floorplan.yaml's beamline is loaded."""
    beamline = yaml.safe_load((location / "config" / "floorplan.yaml").read_text())["beamline"]
    entries = {
        "here": {"name": "here", "beamline": beamline, "active": True, "device_class": "x.SmarAct"},
        "off": {"name": "off", "beamline": beamline, "active": False, "device_class": "x.SmarAct"},
        "elsewhere": {"name": "elsewhere", "beamline": "OTHER", "active": True, "device_class": "x.SmarAct"},
    }
    database = tmp_path / "db.json"
    database.write_text(json.dumps(entries))
    context = FloorPlanContext(config_file=location / "config" / "floorplan.yaml", device_db=database)
    assert context.beamline == beamline
    assert [dev.name for dev in context.devices] == ["here"]
