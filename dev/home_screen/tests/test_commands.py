"""Toolbar commands: multi-command buttons, quoted arguments, and the LAS racks' PDU launches."""

import shlex
from pathlib import Path

import pytest
from conftest import LOCATIONS, PACKAGE_DIR, snapshot
from context import FloorPlanContext
from pdu import RACK_IN_NAME, pdu_macros

LAS = PACKAGE_DIR.parent / "las"


@pytest.fixture
def las() -> FloorPlanContext:
    if LAS not in LOCATIONS:
        pytest.skip("no dev/las")
    return FloorPlanContext(config_file=LAS / "floorplan.yaml", device_db=snapshot(LAS))


def test_toolbar_button_with_several_commands(tmp_path: Path):
    """A button with a command per title: pick one by title, or get one opener per command."""
    toolbar = tmp_path / "toolbar.yaml"
    toolbar.write_text("Tools:\n  buttons:\n    align:\n      titles: [A, B]\n      commands: [run a, run b]\n")
    context = FloorPlanContext(config_file=LAS / "floorplan.yaml", toolbar_file=toolbar, device_db=snapshot(LAS))
    assert context.toolbar_opener("Tools", "align", "B").command == ["run b"]
    both = context.toolbar_opener("Tools", "align")
    assert [(child.title, child.command) for child in both.children] == [("A", ["run a"]), ("B", ["run b"])]
    assert "(missing)" in context.toolbar_opener("Tools", "align", "NOPE").title
    assert "(missing)" in context.toolbar_opener("Tools", "nope").title


def test_quoted_arguments_stay_whole():
    """run_command splits like a shell: a quoted argument (e.g. QRIX's THz 1D-scan) is one argument."""
    command = """/x/launch_1d_scan 'motor="LM1K2:OPA_MP1_DLY1",detector="LM1K2:SRS810:01:X"'"""
    assert shlex.split(command) == ["/x/launch_1d_scan", 'motor="LM1K2:OPA_MP1_DLY1",detector="LM1K2:SRS810:01:X"']


# LAS rack -> the PDU prefix its toolbar button's EDM launch uses (all TrippLite_24)
PDU_PREFIXES = {
    "R01": "LAS:LHN:PWR:05",
    "R03": "LAS:LHN:PWR:02",
    "R06": "LAS:LHN:PWR:06",
    "R07": "LAS:LHN:PWR:07",
    "R08": "LAS:LHN:PWR:01",
    "R13": "LAS:LHN:PWR:04",
    "R18": "LAS:LHN:PWR:03",
}


def test_racks_follow_toolbar_labels(las: FloorPlanContext):
    """Every "(Rxx)" PDU button lands on its rack, and nothing else does."""
    labelled = {}
    for name in las.toolbar["PDUs"]["buttons"]:
        if match := RACK_IN_NAME.search(name):
            labelled.setdefault(match.group(1), []).append(name)
    assert sorted(labelled) == sorted(PDU_PREFIXES)
    for rack in [f"R{n:02d}" for n in range(1, 21)]:
        assert [opener.title for opener in las.rack_openers(rack, {})] == labelled.get(rack, []), rack


@pytest.mark.parametrize("rack,prefix", sorted(PDU_PREFIXES.items()))
def test_pdu_racks_open_the_pdu_screen_with_their_prefix(las: FloorPlanContext, rack: str, prefix: str):
    """The prefix comes from the button's command (R08) or the edm-ioc-*.cmd script it runs (the others)."""
    (opener,) = las.rack_openers(rack, {})
    assert opener.dockable and not opener.command
    assert opener.tooltip.endswith("pdu_tripplite.py")
    commands = las.toolbar["PDUs"]["buttons"][opener.title]["commands"]
    assert pdu_macros(commands) == {"PRE": prefix, "N_CHAN": "24", "IOC": f"IOC:{prefix}"}


def test_other_rack_buttons_run_their_command(las: FloorPlanContext):
    """A button that isn't a TrippLite launch (here a made-up R05 one) runs its command, as before."""
    las.toolbar["PDUs"]["buttons"]["New PDU (R05)"] = {"type": "shell", "commands": ["echo r05"]}
    (opener,) = las.rack_openers("R05", {})
    assert opener.command == ["echo r05"] and not opener.dockable


def test_rack_opens_override(las: FloorPlanContext):
    openers = las.rack_openers("R02", {"opens": [{"device": "las_lhn_bay1_env_sens_1"}]})
    assert [opener.device_name for opener in openers] == ["las_lhn_bay1_env_sens_1"]


def test_pdu_macros_skip_commented_launches(tmp_path: Path):
    script = tmp_path / "edm-ioc-x.cmd"
    script.write_text('# -m "PRE=OLD:PDU" TrippLite_8.edl\nedm -x -m "PRE=NEW:PDU" pduScreens/TrippLite_24.edl &\n')
    # No IOC= in the launch: the screen defaults to IOC:{PRE}
    assert pdu_macros([str(script)]) == {"PRE": "NEW:PDU", "N_CHAN": "24"}
    assert pdu_macros(["echo r05"]) is None
    assert pdu_macros(["/no/such/edm-ioc.cmd"]) is None


def test_toolbar_commands_run_through_run_command(las: FloorPlanContext, no_external_commands):
    """Running an external opener goes to run_command (replaced here, so nothing is launched)."""
    btps = las.toolbar_opener("NEH Beam Transport", "BTPS Overview")
    btps.run()
    assert no_external_commands == ["/cds/group/pcds/epics-dev/screens/pydm/las/bts/run_btps.sh"]
