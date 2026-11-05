# v2: LAS floor-plan home screen (lasdev style)

A proof of concept of the **lasdev** home-screen style applied to the **LAS** PVs: a drawing of the laser hall in which you click a bay, rack or icon to open the matching screen in a `TabDock`. The hall is drawn by Qt from `config/floorplan.yaml`, not from a background image.

How `lasdev` works today is in [lasdev_launch_internals.md](lasdev_launch_internals.md).

**v2 is standalone**: everything it needs is in this directory, so it can be copied as a template for other migrations. It only needs a pcdswidgets (from `PYTHONPATH` or the environment) and PyDM. (v1, the LUCID-style grid, lives in [../v1](../v1) and is not used.)

It has **no runtime dependency on happi, ophyd, pcdsdevices, typhos or lucid**, and nothing outside `dev/` was changed.

## Run it

```bash
pcdswidgets/dev/v2/las_home.sh
```

Environment: `ctrlenv-widgets/v1.2.1`, with this checkout's pcdswidgets and `dev/v2` first on `PYTHONPATH`. **It connects to the real IOCs.**

## What you can click

![floor plan](bg-with%20exp.png)

| Where | Click | Opens |
|---|---|---|
| **Bay 1–4** (the coloured area) | menu | Every control in the bay, as drop-downs: Cameras, SmarAct Motors, Temperature / Humidity (from happi `location_group`), then Shutters, then Tools (that bay's buttons from the LAS toolbar). Each device entry has the dock options; clicking the entry opens it in the dock. Groups have "Open All". |
| **BTS** | menu | BTS cameras, plus the external tools BTPS Overview, BTMS Overview, Laser Hall Vacuum, Shutters, BTS motors, RGA and QPCs (marked ↗). |
| **Racks** with a plug badge (R01, R03, R06, R07, R08, R13, R18) | direct | Runs the LAS toolbar "PDUs" button whose name ends with that rack, e.g. "Zone 1 TiSaph PSU/Chiller PDU (R07)", which opens the IOC's EDM PDU screen in its own window. Matching is automatic: add a toolbar button named "... (R12)" and R12 lights up. |
| Other racks (grey) | — | Tooltip only. No toolbar PDU button names them yet. All 20 racks (R01–R20) are always drawn, so a new "(R05)" button lights up R05 with no other change. |
| **T/H** icons | direct | That environmental sensor (`screens/env_monitor.ui`). |
| **Cameras** / **SmarAct** icons | menu | That bay's cameras or motors (`screens/las_basler.ui`, `screens/smaract.py`). |
| **Shutters** icons | direct or menu | The laser-source shutter screen (new): LS1 in Bay 1, LS3/LS4 in Bay 2, LS5/LS6 in Bay 3, LS8 in Bay 4. |
| **BTPS** icon | direct | Runs the toolbar's "BTPS Overview" (`run_btps.sh`), which opens the btms-ui BTPS screen in its own window. No status dot. |

"Direct" items follow the `TabDock` conventions: a click replaces the current tab, ctrl+click opens a new tab, shift+click opens a new window, and a right click shows the options menu. External tools always open in their own window, since EDM can't be docked.

Each icon uses the same glyph pcdswidgets uses for the screen it opens: `CameraViewerStretch`'s camera, the SmarAct tip/tilt icon, pcdswidgets' fast-shutter symbol, a thermometer, a plug for PDUs, and a shield for BTPS. Each icon also has a small status dot. It shows the worst alarm (typhos colours) across the PVs of everything the icon opens; when it isn't green, hovering the icon also lists the PVs that aren't OK.

The drawing keeps its proportions and scales with the window; text stays sharp at any size. Below 75 % scale the icons drop their labels.

Under the floor plan is the full LAS toolbar (`config/las_toolbar.yaml`, a copy of `lucid_config/LAS_toolbar.yaml`).

## Files

| Path | What it is |
|---|---|
| `bg-with exp.png` | The annotated sketch of what each area should do. Documentation only. |
| `config/floorplan.yaml` | **All layout and behaviour**: the hall drawing (columns left to right, with relative widths, heights and colours; racks generated as R01–R20 in coloured groups of five), icon positions (percent of their area), what each opens, laser source → bay, bay tools, and which toolbar tab racks are matched against. A rack can override the automatic match with its own `opens:` list. Edit this to move or add things; no code changes needed. |
| `floorplan.py` | `FloorPlan` widget, `AreaButton` / `IconButton`, and `FloorPlanContext`, which turns config entries into things to open. |
| `las_home.py` | Home screen: floor plan with the LAS toolbar under it, `TabDock` on the right. |
| `las_home.sh` | Launcher. Puts the pcdswidgets checkout (`PCDSWIDGETS_DIR`, default `../..`) and this directory on `PYTHONPATH`. |
| `devices.py` | Device list from happi's `db.json` read as plain JSON (path from `$LAS_DEVICE_DB` or `$HAPPI_CFG`) or a YAML snapshot; device types (`config/device_types.yaml`); the per-device screen cache. |
| `alarm.py` | `PVAlarmCircle`, the status dot: worst alarm across a list of PVs, in typhos's colours. |
| `screens/smaract.py` | SmarAct screen from the IOC release's own widgets (`common/smaract/R4.0.0/motorScreens`, the release `ioc-las-bts-mcs1` builds against): the expert panel with the advanced-controls tabs (Open-loop, Closed-loop, Diagnostics, Configuration) always shown under it. This is `smaract_expert_screen.py` without the collapsible section and without the PicoScale tab. It uses the release's generated widget classes, because loading `smaract_advanced_controls.ui` directly hits a circular import in that package. |
| `config/device_types.yaml` | Device class → screen, macros, and status PVs: LasBasler → `las_basler.ui`, SmarAct → `smaract.py`, and EnvironmentalMonitor → `env_monitor.ui`. The BTPS isn't listed: it opens through the toolbar and has no status dot. |
| `config/las_toolbar.yaml` | The LAS toolbar (copy of `lucid_config/LAS_toolbar.yaml`, refreshed 2026-11-04). Rack → PDU matching, the bay tools and the BTS tools come from here, by tab and button name. **When deploying, switch to the live file** (`/cds/group/pcds/pyps/apps/hutch-python/lucid_config/LAS_toolbar.yaml`, e.g. via the `TOOLBAR` macro or the default in `floorplan.py`); a renamed button the floor plan refers to then shows as "(missing)". |
| `screens/las_basler.ui`, `screens/env_monitor.ui` | LasBasler camera and environmental monitor screens (built for v1, copied here). |
| `screens/las_basler_settings.ui` | The "LAS Basler Settings" sidebar panel of `las_basler.ui` (manufacturer, sensor, data type, trigger, binning, user sets, reset), embedded there as a `PyDMEmbeddedDisplay` so it can be edited on its own. It inherits the parent's macros (`CAM`); open it alone with `pydm -m CAM=... las_basler_settings.ui`. The embedded display has `minimumSize` width 1 so the sidebar can squeeze it like the other panels (otherwise the PV labels' text width pushes the sidebar wider than its scroll area). |
| `tools/gen_indicator_pvs.py` | **Dev-time only, uses ophyd** (run with the pcds conda python). Regenerates `indicator_pvs` in `config/device_types.yaml`. |
| `tools/export_happi_devices.py` | Regenerates `tests/devices_snapshot.yaml` from happi (`$HAPPI_CFG`, never `$LAS_DEVICE_DB`), sorted by name. No happi import; runs with any python that has PyYAML. |
| `screens/laser_shutter.ui` | **New.** One laser source: LSS opened/closed/permission/request, entry valve, BTPS safe-to-open, destination, override, latched error + Acknowledge, user Open/Close. |
| `tests/` | pytest-qt tests (26). `tests/devices_snapshot.yaml` is a dated snapshot of the 44 active LAS happi entries that the tests use instead of the live database (the screen itself reads the live one). |


## Config entry types (`opens:`)

```yaml
- device: las_lhn_bay1_env_sens_1                        # a happi device, via config/device_types.yaml
- devices: {location: [Bay 3], function: [cameras]}      # all matching happi devices, as a sub-menu
- shutter: LS5                                           # the laser_shutter.ui screen for that source
- screen: laser_shutter.ui                               # any pydm screen in screens/ (or an absolute path)
  macros: {LS: LS1, TITLE: LS1 (Bay 1)}
  title: LS1 Shutter
- toolbar: ["Bays 3/2", "Bay 3 Delay Feedback"]          # run a LAS toolbar button's command (external)
```

One entry means a click opens it directly; several mean a click shows a menu.

## Where the data came from

| What | Source |
|---|---|
| Bay devices | happi `db.json`, grouped by `location_group` and `functional_group`. "Bay 2 - 1um" and "Bay 2 - 800nm" count as Bay 2. "Beam Transport" goes to the BTS area. |
| Rack → PDU | the LAS toolbar "PDUs" tab: each button whose name ends in "(Rxx)" belongs to rack Rxx. |
| Laser source → bay | BTPS screen tab names ("LS3 (Bay 2 1um)", ...) |
| Shutter PVs | `pcdsdevices.lasers.btps` (`LTLHN:LSn:LST:*`, `LTLHN:LSn:BTPS:*`) |
| Bay tools | LAS toolbar "Bays 3/2" tab |

## Tests

```bash
cd pcdswidgets/dev/v2
QT_QPA_PLATFORM=offscreen PYTHONPATH=../..:. \
  /reg/g/pcds/pyps/pixi/ctrlenv-widgets/v1.2.1/src/rhel9-x86_64/.pixi/envs/default/bin/python -m pytest tests -q
```

The tests point channel access at `127.0.0.1` only, use the YAML device snapshot in `config/`, and replace `run_command` so no EDM window is ever launched. They check that:

- every config reference resolves
- every active LAS device appears in exactly one bay or area menu
- the hall config is consistent and every icon sits in a known area
- the drawing lands within a few pixels of the old `bg.png` layout, and icons stay inside their area
- all 20 racks are drawn, racks without a PDU are grey, and a new "(R05)" toolbar button lights up R05
- the menus contain the expected entries
- rack clicks run their PDU toolbar button, icon clicks open the right screen in the dock
- status dots watch the right PVs, and the icon tooltip lists the bad ones
- icons shrink with the drawing
- the new screens load with all macros filled, including embedded displays (forced to load)
- the home screen imports nothing forbidden, and nothing from `dev/v1`

## Known gaps / next steps

- **Not tested against live IOCs.** The shutter PVs have only been checked offline.
- **7 labelled racks have no PDU yet**: R02, R04, R11, R12, R16, R17 and R19. They, and the other unused rack numbers, are drawn grey and light up automatically once the toolbar has a "... (Rxx)" PDU button for them.
- **Racks open only the PDU.** The sketch mentions "maybe some monitoring, or all of the controls in it". Rack entries already accept a list of `opens`, so adding more is a config change.
- **Icon positions are rough**, as the sketch says. Fine-tune them in `floorplan.yaml` (`at: [x %, y %]` within their area).
- **SmarAct screens are pinned to R4.0.0.** When `ioc-las-bts-mcs1` moves to a new release, update `SMARACT_SCREENS` in `screens/smaract.py`, or pass it as a macro.
- **Mixed data sources.** Rack → PDU comes from the toolbar labels, while `ioc-las-lhn-pwr-02.cfg` says "LHN Timing PDU Bay 2" for the PDU the toolbar calls "Zone 2 OPCPA Controls PDU (R03)". Confirm with the LAS team.
