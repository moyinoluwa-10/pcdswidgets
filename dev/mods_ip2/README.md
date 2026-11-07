# IP2 MODS (LM2K4) floor-plan home screen

A pcdswidgets rebuild of the `mods_ip2` home screen: a drawing of the IP2 MODS table, with its optical stations in beam order: INJ (Injection) → COM (Compression) → HRM (Harmonics) → ATM (Arrival Time Monitor) → EJX (Ejection). Click a station or an icon to open the matching screen in a `TabDock`. It is a copy of `dev/mods_ip1` (same code and screens) with the IP2_MODS config: its floor plan, toolbar and happi snapshot.

**This directory is only the location's config**: `config/floorplan.yaml` (the drawing, what each click opens, and its happi `beamline`, window `title` and `toolbar`), the toolbar copy, and the launcher. The screen itself (code, device screens, `device_types.yaml`, tools) is the shared [home_screen](../home_screen/README.md) package, the same for every location.

It has **no runtime dependency on happi, ophyd, pcdsdevices, typhos or lucid**, and nothing outside `dev/` was changed.

## Run it

```bash
pcdswidgets/dev/mods_ip2/mods_ip2_home.sh &      # foreground without "&", like the production launchers
pcdswidgets/dev/mods_ip2/mods_ip2_home.sh -m '{"TOOLBAR": "/cds/group/pcds/pyps/apps/hutch-python/lucid_config/IP2_MODS_toolbar.yaml"}' &   # live toolbar
```

Environment: `ctrlenv-widgets/v1.2.1`, with this checkout's pcdswidgets and `dev/home_screen` first on `PYTHONPATH`. **It connects to the real IOCs.**

## What `mods_ip2` runs today

```
mods_ip2                                  (bash function, /cds/group/pcds/setup/pcds_shortcuts.sh:416)
 ├─ subnet_check ip2 las tmo              (read-only / write-enabled message)
 └─ $PYPS_SITE_TOP/config/las/mods_ip2_home.sh &
      └─ $EPICS_SETUP/lucid-launcher.sh IP2_MODS          ("Option 2: lucid launcher with dev_conda")
           └─ lucid IP2_MODS --toolbar=$LUCID_CONFIG/IP2_MODS_toolbar.yaml
```

LUCID builds a grid of every active happi device with `beamline: IP2_MODS`, grouped by `location_group` × `functional_group`, and opens typhos screens. This rebuild uses the same happi data, the same toolbar and the same `subnet_check`.

## What you can click

![floor plan](floorplan.png)

| Where | Click | Opens |
|---|---|---|
| **Station** (INJ, COM, HRM, ATM, EJX) | menu | Every control in the station, as drop-downs by function (Cameras, SmarAct Motors, Spectrometers, Elliptecs, Temperature / Humidity), then Tools (that station's toolbar buttons). Groups have "Open All". |
| **Cameras** / **SmarAct** / **Spectrometer** / **Elliptecs** icons | menu | That station's devices of that function. |
| **T/H** icons (INJ, COM, HRM) | direct | That station's environmental sensor (`home_screen/screens/env_monitor.ui`). ATM and EJX have none in happi. |
| **Shutter** icons (ATM, EJX) | direct | The toolbar's "ATM / EJX non-LSS Shutter" (opens in its own window). No status dot. |

Station → happi location groups: INJ `1_lm2k4_inj`, COM `2_lm2k4_com`, HRM `3_lm2k4_hrm`, ATM `4_lm2k4_atm`, EJX `5_lm2k4_ejx`. Station tools: ATM and EJX their non-LSS shutter. The other toolbar buttons (LCLS Home, Cam Viewer, the digitizers, iocmanager, Dispersion Scan) are only in the toolbar.

"Direct" items follow the `TabDock` conventions: a click replaces the current tab, ctrl+click opens a new tab, shift+click opens a new window, and a right click shows the options menu. External tools always open in their own window.

Each icon has a small status dot: the worst alarm (typhos colours) across the PVs of everything it opens. When it isn't green, hovering the icon also lists the PVs that aren't OK. The drawing keeps its proportions and scales with the window; below 75 % scale the icons drop their labels.

Under the floor plan is the full IP2_MODS toolbar (`config/ip2_mods_toolbar.yaml`, a copy of `lucid_config/IP2_MODS_toolbar.yaml`).

## Device screens

45 active devices, 9 classes:

| Class | Count | Screen |
|---|---|---|
| `SmarAct` | 14 | `home_screen/screens/smaract.py`, the IOC release's own widgets (`common/smaract/R4.0.0`) |
| `LasBasler` | 11 | `home_screen/screens/las_basler.ui` (camera viewer + settings panel `home_screen/screens/las_basler_settings.ui`) |
| `SmarActEncodedTipTilt` (7), `SmarActTipTilt` (1) | 8 | `home_screen/screens/tip_tilt.py`, pcdswidgets' `MotorTipTiltDouble`: d-pad, step size and position per axis, invert, per-axis expert buttons. Tip (`{prefix}{tip_pv}`) is left/right, tilt is up/down. The encoded stages (`STYLE: MotorRecord`) use their motor records; the open-loop one (COM MR4) the SmarAct step fields |
| `EllLinear` (4), `Ell9` (2), `EllRotation` (1) | 7 | `home_screen/screens/elliptec.py` + `elliptec.ui`, one screen for every Thorlabs Elliptec (thorlabs-ell IOC, PVs `{prefix}:M{channel}:...`). The `STAGE` macro (`continuous`, `ell6`, `ell9`) drops the sections whose records that stage type doesn't load. Scrolls in a short dock |
| `EnvironmentalMonitor` | 3 | `home_screen/screens/env_monitor.ui` |
| `QminiSpectrometer` | 2 | `home_screen/screens/qmini.py`, the IOC release's own embedded screen (`common/qmini/R3.1.1/qminiScreens/QminiSpectrometer.embedded.py`). Scrolls in a short dock |

`home_screen/config/device_types.yaml` is mods_ip1's, without the power meter (`El3174AiCh`, none in IP2_MODS). It keeps `Ell6`, which `elliptec.py` supports, so an Ell6 added to happi just works.

Every active class has a screen. A class without `screen:` in `home_screen/config/device_types.yaml` opens a placeholder (name, class, prefix, "no screen yet") and still has a status dot.

### Per-device happi kwargs

Tip/tilt stages and Elliptecs can't be described by `{prefix}` alone: their PVs depend on happi kwargs (`tip_pv: '{{ioc_tip_suffix}}'`, `channel: '{{ioc_channel}}'`, `port: '15'`). `devices.py` keeps each entry's kwargs, with the `{{field}}` templates filled in from the entry, and makes them available as `{tip_pv}`, `{channel}`, ... in `device_types.yaml`. For example, `LM2K4:COM_MP2_MR4` with `tip_pv: _TIP1` gives `{prefix}{tip_pv}:STEP_COUNT` → `LM2K4:COM_MP2_MR4_TIP1:STEP_COUNT`. `home_screen/tools/gen_indicator_pvs.py` builds such classes with the placeholders listed under `template_kwargs:`.

## Files

| Path | What it is |
|---|---|
| [`../home_screen/`](../home_screen/README.md) | The shared package: home screen, floor-plan code, every device screen, `home_screen/config/device_types.yaml` (device class → screen, macros, status PVs) and the tools (`gen_indicator_pvs.py`, `export_happi_devices.py`). |
| `config/floorplan.yaml` | **All layout and behaviour**: the drawing (stations left to right, relative widths/heights, colours, preferred height), station → location groups and tools, icon positions (percent of their station) and what each opens. Edit this to move or add things; no code changes needed. |
| `mods_ip2_home.sh` | Launcher: sets this location's `subnet_check` arguments and runs `../home_screen/launch_home.sh` with `config/floorplan.yaml` (ctrlenv-widgets, this checkout's pcdswidgets and the package on `PYTHONPATH`; `HOME_SCREEN_DIR` to use another copy of the package). |
| `config/ip2_mods_toolbar.yaml` | The toolbar (copy of `lucid_config/IP2_MODS_toolbar.yaml`, taken 2026-11-05). Station tools and shutter icons refer to it by tab, button and title. **When deploying, switch to the live file** (e.g. via the `TOOLBAR` macro); a renamed button the floor plan refers to then shows as "(missing)". |
| `floorplan.png` | Screenshot of the floor plan (documentation only). |

## Config entry types (`opens:`)

```yaml
- device: lm2k4_inj_env_sens                                  # a happi device, via config/device_types.yaml
- devices: {location: [5_lm2k4_ejx], function: [elliptecs]}   # all matching happi devices, as a sub-menu
- screen: env_monitor.ui                                      # any pydm screen in screens/ (or an absolute path)
  macros: {PREFIX: LM2K4:INJ_BHC_AI_01, NAME: inj}
  title: INJ T/H
- toolbar: [Tools, EJX non-LSS Shutter]                       # run a toolbar button's command (external)
- toolbar: [Tools, <button>, <title>]                         # one command of a button with several titles
```

One entry means a click opens it directly; several mean a click shows a menu.

## Tests

This location has no tests of its own: the [home_screen](../home_screen/README.md#tests) package's core tests check every location's `config/floorplan.yaml` (references resolve, every happi device is in exactly one menu, status PVs are filled in, toolbar commands) against its toolbar and its happi snapshot, `home_screen/tests/snapshots/mods_ip2.yaml`.

## Known gaps / next steps

- **Spectrometer status dots watch big waveforms.** `QminiSpectrometer`'s generated `indicator_pvs` include `:SPECTRUM` and `:WAVELENGTHS` (the same signals typhos watched). They work, but each update is a full array; trimming them to `:STATUS` / `:W0_FIT` would be cheaper. `gen_indicator_pvs.py` would put them back on the next run, so this needs a small exclude option there first.
- **Station layout is schematic** (equal boxes in beam order), not the real table. Fine-tune widths, heights and icon positions in `config/floorplan.yaml`, or replace with a sketch of the table.
- **Not yet tried against the live LM2K4 IOCs.** The code and screens are the ones tested live on IP1; the IP2 config (floor plan, snapshot, toolbar) has only been checked offline.
