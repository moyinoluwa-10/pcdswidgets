"""Each location's floorplan.yaml against its toolbar and happi devices (every location, through the package)."""

import json
from pathlib import Path

import pytest
from conftest import floorplan_config
from floorplan import FloorPlanContext, rack_names


def area_openers(context: FloorPlanContext) -> dict[str, list]:
    """What every drawn area opens (stations, bays, areas and racks), by area name."""
    config = context.config
    openers = {}
    for column in config["hall"]["columns"]:
        if "station" in column:
            name = column["station"]
            openers[name] = context.station_openers(name, config.get("stations", {}).get(name, {}))
        elif "bay" in column:
            name = column["bay"]
            openers[name] = context.bay_openers(name, config.get("bays", {}).get(name, {}))
        elif "area" in column:
            name = column["area"]
            openers[name] = context.resolve(config.get("areas", {}).get(name, {}).get("opens", []))
        elif "racks" in column:
            for group in column["racks"]:
                for rack in rack_names(group["range"]):
                    openers[rack] = context.rack_openers(rack, (config.get("racks") or {}).get(rack, {}))
    return openers


def leaves(openers: list) -> list:
    return [leaf for opener in openers for leaf in opener.leaves()]


def test_config_names_beamline_title_and_toolbar(location: Path):
    config = floorplan_config(location)
    assert config["beamline"] and config["title"]
    assert (location / "config" / config["toolbar"]).is_file()


def test_hall_columns_are_consistent(context: FloorPlanContext):
    for column in context.config["hall"]["columns"]:
        kinds = {"gap", "station", "bay", "area", "racks"} & set(column)
        assert len(kinds) == 1, column
        if "top" in column and "height" in column:
            assert 0 <= column["top"] and column["top"] + column["height"] <= 100, column


def test_icons_sit_in_known_areas(context: FloorPlanContext):
    areas = area_openers(context)
    for icon in context.config.get("icons", []):
        assert icon["in"] in areas, icon
        assert all(0 <= value <= 100 for value in icon.get("at", [50, 50])), icon


def test_every_reference_resolves(context: FloorPlanContext):
    """Every device, screen and toolbar button the config names exists ("(missing)" otherwise)."""
    for icon in context.config.get("icons", []):
        found = leaves(context.resolve(icon["opens"]))
        assert found, icon
        assert all(leaf.dockable or leaf.command for leaf in found), icon
        assert not [leaf.title for leaf in found if "(missing)" in leaf.title], icon
    for name, openers in area_openers(context).items():
        assert not [leaf.title for leaf in leaves(openers) if "(missing)" in leaf.title], name
        for leaf in leaves(openers):
            if leaf.dockable and leaf.tooltip.endswith((".ui", ".py")):
                assert Path(leaf.tooltip).is_file(), (name, leaf.tooltip)


def test_every_device_is_in_exactly_one_area(context: FloorPlanContext):
    """Every active happi device is in one area's menu, once; the BTPS opens through the LAS toolbar instead."""
    seen = [leaf.device_name for openers in area_openers(context).values() for leaf in leaves(openers)]
    seen = [name for name in seen if name]
    expected = [dev.name for dev in context.devices if not dev.device_class.endswith("BtpsState")]
    assert sorted(seen) == sorted(expected)


def test_status_pvs_are_filled_in(context: FloorPlanContext):
    """Status dots watch real PVs: every per-device template (prefix, tip_pv, channel, ...) is filled in."""
    for icon in context.config.get("icons", []):
        channels = [address for opener in context.resolve(icon["opens"]) for address in opener.all_channels()]
        assert not [address for address in channels if "{" in address], icon
        assert all(address.startswith(("ca://", "calc://")) for address in channels), icon


def test_context_loads_its_beamline_from_a_happi_database(location: Path, tmp_path: Path):
    """With a happi JSON database (what the launchers use), only the floorplan.yaml's beamline is loaded."""
    beamline = floorplan_config(location)["beamline"]
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


def test_context_needs_a_floorplan(monkeypatch):
    monkeypatch.delenv("HOME_FLOORPLAN", raising=False)
    with pytest.raises(RuntimeError, match="HOME_FLOORPLAN"):
        FloorPlanContext()
