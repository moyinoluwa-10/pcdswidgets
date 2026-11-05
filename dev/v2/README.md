# v2: LAS floor-plan home screen (lasdev style)

A proof of concept of the **lasdev** home-screen style applied to the **LAS** PVs: a drawing of the laser hall in which you click a bay, rack or icon to open the matching screen in a `TabDock`.

How `lasdev` works today is in [lasdev_launch_internals.md](lasdev_launch_internals.md). v1 (the LUCID-style grid) is in [../v1](../v1).

Like v1, it has **no runtime dependency on happi, ophyd, pcdsdevices, typhos or lucid**, and nothing outside `dev/` was changed.

## Run it

```bash
pcdswidgets/dev/v2/las_home.sh
```

The environment is the same as v1: `ctrlenv-widgets/v1.2.1`, this checkout's pcdswidgets first, plus `dev/v2` and `dev/v1` on `PYTHONPATH`. **It connects to the real IOCs.**

## What you can click

![floor plan](bg-with%20exp.png)

| Where | Click | Opens |
|---|---|---|
| **Bay 1–4** (the coloured area) | menu | Every control in the bay, as drop-downs: Cameras, SmarAct Motors, Temperature / Humidity (from happi `location_group`), then Shutters, then Tools (that bay's buttons from the LAS toolbar). Each device entry has the dock options; clicking the entry opens it in the dock. Groups have "Open All". |
| **BTS** | menu | BTS cameras, plus the external tools BTPS Overview, BTMS Overview, Laser Hall Vacuum, Shutters, BTS motors, RGA and QPCs (marked ↗). |
| **Racks** with a plug badge (R01, R03, R06, R07, R08, R13, R18) | direct | That rack's TrippLite PDU screen (new, PyDM). |
| Other racks | — | Tooltip only. No PDU is known for them yet. |
| **T/H** icons | direct | That environmental sensor (v1 screen). |
| **Cameras** / **SmarAct** icons | menu | That bay's cameras or motors (v1 screens). |
| **Shutters** icons | direct or menu | The laser-source shutter screen (new): LS1 in Bay 1, LS3/LS4 in Bay 2, LS5/LS6 in Bay 3, LS8 in Bay 4. |
| **BTPS** icon | direct | Runs the toolbar's "BTPS Overview" (`run_btps.sh`), which opens the btms-ui BTPS screen in its own window. The status dot still watches the BTPS PVs. |

"Direct" items follow the `TabDock` conventions: a click replaces the current tab, ctrl+click opens a new tab, shift+click opens a new window, and a right click shows the options menu. External tools always open in their own window, since EDM can't be docked.

Each icon uses the same glyph pcdswidgets uses for the screen it opens: `CameraViewerStretch`'s camera, the SmarAct tip/tilt icon, pcdswidgets' fast-shutter symbol, a thermometer, a plug for PDUs, and a shield for BTPS. Each icon also has a small status dot. It works like v1's grid circle (typhos colours), summarising the PVs of everything the icon opens.

The image scales with the window, and so do the click areas. Below 75 % scale the icons drop their labels.

Under the floor plan is the full LAS toolbar (v1's copy of `LAS_toolbar.yaml`), placed as in v1.

## Files

| Path | What it is |
|---|---|
| `bg.png` | The floor plan drawing (1356 × 672). Click areas are measured from its coloured shapes. |
| `bg-with exp.png` | The annotated sketch of what each area should do. Documentation only. |
| `config/floorplan.yaml` | **All layout and behaviour**: bay/BTS/rack rectangles, icon positions, what each opens, rack → PDU, laser source → bay, bay tools. Edit this to move or add things; no code changes needed. |
| `floorplan.py` | `FloorPlan` widget, `AreaButton` / `IconButton`, and `FloorPlanContext`, which turns config entries into things to open. |
| `las_home.py` | Home screen: floor plan with the LAS toolbar under it, `TabDock` on the right (v1's arrangement, with the floor plan in place of the grid). |
| `las_home.sh` | Launcher. |
| `screens/pdu_tripplite.py` | **New.** TrippLite PDU (pdu_snmp `TrippLitePdu_24.db`): name, location, model, status, input/output power, and per outlet: name, state, controllable, last command, and On / Off / Cycle buttons. |
| `screens/smaract_r4.py` | SmarAct screen from the IOC release's own widgets (`common/smaract/R4.0.0/motorScreens`, the release `ioc-las-bts-mcs1` builds against): the expert panel with the advanced-controls tabs (Open-loop, Closed-loop, Diagnostics, Configuration) always shown under it. This is `smaract_expert_screen.py` without the collapsible section and without the PicoScale tab. It uses the release's generated widget classes, because loading `smaract_advanced_controls.ui` directly hits a circular import in that package. |
| `config/device_types.yaml` | v2-only overrides of v1's device types (currently: SmarAct → `smaract_r4.py`). Keys left out, such as `indicator_pvs`, come from v1. v1 is unchanged. |
| `screens/laser_shutter.ui` | **New.** One laser source: LSS opened/closed/permission/request, entry valve, BTPS safe-to-open, destination, override, latched error + Acknowledge, user Open/Close. |
| `tests/` | pytest-qt tests (19). |

From v1 (used as-is, not copied, except for the overrides above): `las_devices.py`, `las_grid.py` (`DeviceScreenCache`, `PVAlarmCircle`), the device screens and `device_types.yaml`, the toolbar YAML, and `bin/las-open-device`. (v1's copied BTPS screens are no longer used by v2.)

## Config entry types (`opens:`)

```yaml
- device: las_lhn_bay1_env_sens_1                        # a happi device, via v1's device_types.yaml
- devices: {location: [Bay 3], function: [cameras]}      # all matching happi devices, as a sub-menu
- shutter: LS5                                           # the laser_shutter.ui screen for that source
- screen: pdu_tripplite.py                               # any pydm screen in screens/ (or an absolute path)
  macros: {PRE: LAS:LHN:PWR:07}
  title: R07 PDU
- toolbar: ["Bays 3/2", "Bay 3 Delay Feedback"]          # run a LAS toolbar button's command (external)
  status: las_btps                                       # optional: status dot watches that device's PVs
```

One entry means a click opens it directly; several mean a click shows a menu.

## Where the data came from

| What | Source |
|---|---|
| Bay devices | happi `db.json` (as in v1), grouped by `location_group` and `functional_group`. "Bay 2 - 1um" and "Bay 2 - 800nm" count as Bay 2. "Beam Transport" goes to the BTS area. |
| Rack → PDU | the LAS toolbar "PDUs" tab names the rack for each PDU (e.g. "Zone 1 TiSaph PSU/Chiller PDU (R07)"). PV prefixes and the model (TrippLite, 24 outlets) come from `ioc-las-pdu_snmp/ioc-las-lhn-pwr-0N.cfg`. |
| PDU PVs | `pdu_snmp/R3.1.0/db/TrippLitePdu_24.db`, plus the PVs used by `pduScreens/TrippLite_24.edl` |
| Laser source → bay | BTPS screen tab names ("LS3 (Bay 2 1um)", ...) |
| Shutter PVs | `pcdsdevices.lasers.btps` (`LTLHN:LSn:LST:*`, `LTLHN:LSn:BTPS:*`) |
| Bay tools | LAS toolbar "Bays 3/2" tab |

## Tests

```bash
cd pcdswidgets/dev/v2
QT_QPA_PLATFORM=offscreen PYTHONPATH=../..:.:../v1 \
  /reg/g/pcds/pyps/pixi/ctrlenv-widgets/v1.2.1/src/rhel9-x86_64/.pixi/envs/default/bin/python -m pytest tests -q
```

The tests point channel access at `127.0.0.1` only, use v1's YAML device snapshot, and replace `run_command` so no EDM window is ever launched. They check that:

- every config reference resolves
- every active LAS device appears in exactly one bay or area menu
- all geometry is inside the image
- at full size the click areas match the config exactly
- the menus contain the expected entries
- rack and icon clicks open the right screen in the dock
- status dots watch the right PVs
- icons shrink with the image
- the new screens load with all macros filled
- the home screen imports nothing forbidden

## Known gaps / next steps

- **Not tested against live IOCs.** The PDU screen's scaled values (`calc://`) and the shutter PVs have only been checked offline.
- **The PDU screen has write buttons.** Every outlet command asks for confirmation. The whole-PDU on/off/reboot controls were left out on purpose.
- **7 labelled racks have no PDU yet**: R02, R04, R11, R12, R16, R17 and R19. The 10 grey slots are unlabelled. Add a `pdu:` line in `floorplan.yaml` once known. All 7 LHN PDUs in the IOC configs (`LAS:LHN:PWR:01..07`) are already placed.
- **Racks open only the PDU.** The sketch mentions "maybe some monitoring, or all of the controls in it". Rack entries already accept a list of `opens`, so adding more is a config change.
- **Icon positions are rough**, as the sketch says. Fine-tune them in `floorplan.yaml`.
- **SmarAct screens are pinned to R4.0.0.** When `ioc-las-bts-mcs1` moves to a new release, update `SMARACT_SCREENS` in `screens/smaract_r4.py`, or pass it as a macro.
- **Mixed data sources.** Rack → PDU comes from the toolbar labels, while `ioc-las-lhn-pwr-02.cfg` says "LHN Timing PDU Bay 2" for the PDU the toolbar calls "Zone 2 OPCPA Controls PDU (R03)". Confirm with the LAS team.
