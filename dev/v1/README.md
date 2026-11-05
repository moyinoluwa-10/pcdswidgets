# v1: LAS home screen on pcdswidgets (dev)

A rebuild of the LUCID LAS home screen (`las` in a terminal) using pcdswidgets, with **no runtime dependency on happi, ophyd, pcdsdevices, typhos, or lucid**.

How the current `las` command works is written up in [las_launch_internals.md](las_launch_internals.md).

Everything lives in this directory. Nothing outside `dev/` was changed: shared files (happi `db.json`, `lucid_config`, `/reg/g/pcds/pyps/config/las/las_home.sh`, the pixi envs) are only read.

## Run it

```bash
pcdswidgets/dev/v1/las_home.sh
```

This activates `ctrlenv-widgets/v1.2.1` (PyDM 1.29, which has none of the forbidden packages installed), puts this checkout's `pcdswidgets` and `dev/` first on `PYTHONPATH`, prints the same read-only / write-enabled message as `las`, and starts `pydm` in the background.

**It connects to the real IOCs.** Write access is whatever channel access security gives your host, the same as LUCID.

Options:

| Variable | Effect |
|---|---|
| `ENVVER=latest-released` | use a different `ctrlenv-widgets` version |
| `LAS_DEVICE_DB=dev/v1/config/las_devices.yaml` | use the YAML snapshot instead of the live happi `db.json` |

Open one device screen without the home screen (replaces `typhos <name>`):

```bash
dev/v1/bin/las-open-device las_lhn_bay1_cam_ff
dev/v1/bin/las-open-device --print las_bts_mcs2_01_m1   # show the pydm command only
```

## What's here

| Path | What it is |
|---|---|
| `las_home.sh` | Launcher. Dev version of "Option 4: pydm home with pixi" in the org `las_home.sh`. |
| `las_home.py` | Home screen (PyDM `Display`). Same layout and resize behaviour as `LucidMainWindow`: grid top-left, toolbar bottom-left, 850 px `TabDock` on the right, "small window mode" placeholder when narrow. |
| `las_grid.py` | `LasIndicatorGrid`: subclasses pcdswidgets' `IndicatorGrid` / `IndicatorCell` / `IndicatorGroup`, so menus, keybindings and docking are unchanged. Swaps happi → JSON, `TyphosAlarmCircle` → `PVAlarmCircle`, typhos screens → pydm screens. |
| `las_devices.py` | Reads happi's `db.json` as plain JSON (path from `$LAS_DEVICE_DB` or `$HAPPI_CFG`), or a YAML snapshot. Filters `beamline=LAS, active=True`, like `cli.search`. |
| `open_device.py`, `bin/las-open-device` | Open a device screen by happi name. |
| `config/device_types.yaml` | Device class → screen file, macros, and indicator PVs. |
| `config/las_toolbar.yaml` | Copy of `lucid_config/LAS_toolbar.yaml` (snapshot, 2026-10-21). |
| `config/las_devices.yaml` | Snapshot of the 44 active LAS happi entries (used by the tests). |
| `screens/las_basler.ui` | **New.** LasBasler camera: `CameraViewerStretch` + Acquisition, Exposure, Centroid, ROI, Markers, Colormap, and a new LAS Basler Settings panel (user sets, data type, trigger, event code, binning, Cross4 target, packet size, reset). |
| `screens/smaract_detailed.ui` | **New.** SmarAct: `MotorClassicFull` + motor-record config (limits, velocity, offset, homing) + SmarAct channel (positioner type, calibration, state, temperatures) + `SmaractOpenLoopContextDouble`. |
| `screens/env_monitor.ui` | **New.** EnvironmentalMonitor: pressure / humidity / temperature, with value, raw ADC, slope, offset, conversion and precision. |
| `screens/btps/` | Copies of `pcdsdevices/ui/btps*.ui` (already pure PyDM). One change: the `typhos ${HAPPI_DEVICE}` button in `btps-range-summary.ui` now runs `las-open-device ${HAPPI_DEVICE}`. |
| `tools/gen_indicator_pvs.py` | **Dev-time only, uses ophyd.** Regenerates `indicator_pvs` in `device_types.yaml`. |
| `tools/export_happi_devices.py` | Regenerates `config/las_devices.yaml`. No happi import. |
| `tests/` | pytest-qt tests (18). |

## How the grid matches LUCID

- **Devices and layout**: same query (`beamline=LAS`, `active=True`), same grouping keys, same alphabetical row/column sort. That gives the same 44 devices, 4 rows and 7 columns.
- **Indicator colour**: `PVAlarmCircle` uses typhos's colours and rules: the worst severity across PVs, with disconnected counting as worst. Green no alarm, yellow minor, red major, magenta invalid, white disconnected.
- **Which PVs each indicator watches**: LUCID's circle watches a device's *hinted* signals if it has any, otherwise *hinted + normal*. `gen_indicator_pvs.py` builds each class with ophyd once and records exactly those PVs:

  | Class | Level | PVs |
  |---|---|---|
  | LasBasler | normal | 10 (Acquire, DetectorState, Model, image counter, Stats2 centroid/sigma, Cross4 target) |
  | SmarAct | hinted | 1 (`.RBV`) |
  | EnvironmentalMonitor | normal | 3 (`:1/:2/:3.VAL`) |
  | BtpsState | hinted | 732 (all LS/LD range checks, valves, stage readbacks) |

  LasBasler also has two non-EPICS signals (`auto_configure`, `cam_viewer`). typhos treats those as always connected with no alarm, so leaving them out doesn't change the colour.

## Adding a device class

1. Build a screen in `screens/` with Designer, using `${MACRO}` placeholders.
2. Add the class to `config/device_types.yaml` with `screen`, `macros` and `indicator_pvs`. Macro templates: `{name}`, `{prefix}`, `{prefix_nocolon}`, `{doc}`, `{dev}`.
3. To regenerate `indicator_pvs` (needs an env with the class's ophyd code, e.g. the shared pcds conda):

   ```bash
   /cds/group/pcds/pyps/conda/py312/envs/pcds-6.0.1/bin/python -I dev/v1/tools/gen_indicator_pvs.py
   ```

A class with no entry still appears in the grid. Clicking it opens a placeholder that shows its happi metadata.

## Tests

```bash
cd pcdswidgets/dev/v1
QT_QPA_PLATFORM=offscreen PYTHONPATH=../..:. \
  /reg/g/pcds/pyps/pixi/ctrlenv-widgets/v1.2.1/src/rhel9-x86_64/.pixi/envs/default/bin/python -m pytest tests -q
```

The tests point channel access at `127.0.0.1` only and use the YAML snapshot, so they never contact a real IOC. The suite checks that:

- every device class has a screen
- every screen loads with all macros filled
- the camera sidebar adopts all 7 panels
- no BTPS screen calls typhos
- the alarm logic is correct
- the full home screen loads in a fresh interpreter without importing happi, ophyd, pcdsdevices, typhos or lucid

## Known gaps / next steps

- **Not tested against live IOCs.** Everything above was checked offscreen with CA blocked. Next, run `las_home.sh` on a LAS console and compare it side by side with `las`.
- **las-console access-rights bug.** LUCID's `setup_rw_hack` forces an access-rights refresh after reconnects, because PVs on las-console sometimes come back without read/write access. That hack patches ophyd signals. PyDM widgets talk to pyepics directly and may still hit the bug. Watch for widgets stuck in the disconnected/read-only state after roughly 4 hours on las-console. If it happens, the fix belongs in a PyDM data-plugin hook.
- **Toolbar and screen copies drift.** `config/las_toolbar.yaml` and `screens/btps/` are snapshots. Re-copy them, or point `TOOLBAR=` at the live file (`pydm -m '{"TOOLBAR": "..."}' dev/v1/las_home.py`).
- **BTPS LS6 links.** `btps-source-tabs.ui` names `las_bts_mcs2_01_m16`–`m18`, which are not in happi, so those three "open device" buttons fail. They fail with `typhos` today too.
- **Not done yet:** LUCID's splash screen and centralized PCDS logging. Neither is needed for function. The slow part of LUCID's start-up, instantiating ophyd devices, is gone.
- **Promoting to pcdswidgets proper**: move the screens into `pcdswidgets/screens/` and `pcdswidgets/ui/`, and consider an upstream `devices_loader` hook on `IndicatorGrid`, so `las_grid.py` doesn't need to copy `add_devices` and `_add_group`.
