# IP1 MODS (LM1K4) floor-plan home screen

A pcdswidgets rebuild of the `mods_ip1` home screen: a drawing of the IP1 MODS table, with its optical stations in beam order: INJ (Injection) → COM (Compression) → OPA (Optical Parametric Amplification) → HRM (Harmonics) → ATM (Arrival Time Monitor) → EJX (Ejection). Click a station or an icon to open the matching screen in a `TabDock`. It is built from the `dev/las` template and follows the same structure.

**This directory is only the location**: `floorplan.yaml` (the drawing, what each click opens, and its happi `beamline`, window `title` and `toolbar`), `mods_ip1_home.py` (the home screen) and `mods_ip1_home.sh` (dev launcher). The screen itself (code, device screens, `device_types.yaml`, tools) is the shared [home_screen](../home_screen/README.md) package, the same for every location.

It has **no runtime dependency on happi, ophyd, pcdsdevices, typhos or lucid**, and nothing outside `dev/` was changed.

## Run it

```bash
pcdswidgets/dev/mods_ip1/mods_ip1_home.sh &      # foreground without "&", like the production launchers
```

Environment: `ctrlenv-widgets/v1.2.1`, with this checkout's pcdswidgets first on `PYTHONPATH`. In production (the org launcher's "Option 4"), from this directory: `pydm --hide-nav-bar --hide-menu-bar --hide-status-bar mods_ip1_home.py`. **It connects to the real IOCs.**

## What `mods_ip1` runs today

```
mods_ip1                                  (bash function, /cds/group/pcds/setup/pcds_shortcuts.sh:409)
 ├─ subnet_check ip1 las tmo              (read-only / write-enabled message)
 └─ $PYPS_SITE_TOP/config/las/mods_ip1_home.sh &
      └─ $EPICS_SETUP/lucid-launcher.sh IP1_MODS          ("Option 2: lucid launcher with dev_conda")
           └─ lucid IP1_MODS --toolbar=$LUCID_CONFIG/IP1_MODS_toolbar.yaml
```

LUCID builds a grid of every active happi device with `beamline: IP1_MODS`, grouped by `location_group` × `functional_group`, and opens typhos screens. This rebuild uses the same happi data, the same toolbar and the same `subnet_check`.

## What you can click

![floor plan](floorplan.png)

| Where | Click | Opens |
|---|---|---|
| **Station** (INJ, COM, OPA, HRM, ATM, EJX) | menu | Every control in the station, as drop-downs by function (Cameras, SmarAct Motors, Spectrometers, Elliptecs, Power Meters, Temperature / Humidity), then Tools (that station's toolbar buttons). Groups have "Open All". |
| **Cameras** / **SmarAct** / **Spectrometer** / **Elliptecs** / **Power** icons | menu | That station's devices of that function. |
| **T/H** icons | direct | That station's environmental sensor (`home_screen/screens/env_monitor.ui`). |
| **Shutter** icons (ATM, EJX) | direct | The toolbar's "ATM / EJX non-LSS Shutter" (opens in its own window). No status dot. |

Station → happi location groups: INJ `1_lm1k4_inj`, COM `2_lm1k4_com`, OPA `3_lm1k4_opa`, HRM `3_lm1k4_hrm` + `4_lm1k4_hrm` + `4_lm1k4_int`, ATM `5_lm1k4_atm`, EJX `6_lm1k4_ejx`. Station tools: INJ "WFS Expert Screen"; COM and ATM their own "nf-ff-alignment" command (COM_DP1 / ATM_DP1); ATM and EJX their non-LSS shutter.

"Direct" items follow the `TabDock` conventions: a click replaces the current tab, ctrl+click opens a new tab, shift+click opens a new window, and a right click shows the options menu. External tools always open in their own window.

Each icon has a small status dot: the worst alarm (typhos colours) across the PVs of everything it opens. When it isn't green, hovering the icon also lists the PVs that aren't OK. The drawing keeps its proportions and scales with the window; below 75 % scale the icons drop their labels.

Under the floor plan is the full IP1_MODS toolbar (the live `lucid_config/IP1_MODS_toolbar.yaml`).

## Device screens

59 active devices, 11 classes:

| Class | Count | Screen |
|---|---|---|
| `SmarAct` | 14 | `home_screen/screens/smaract.py`, the IOC release's own widgets (`common/smaract/R4.0.0`, what `ioc-lm1k4-mcs2-*` build against) |
| `LasBasler` | 13 | `home_screen/screens/las_basler.ui` (camera viewer + settings panel `home_screen/screens/las_basler_settings.ui`) |
| `QminiSpectrometer` | 6 | `home_screen/screens/qmini.py`, the IOC release's own embedded screen, what LUCID opens (`common/qmini/R3.1.1/qminiScreens/QminiSpectrometer.embedded.py`): spectrum and fit plot, single exposure, save spectrum; "Parameters" / "Fit Settings" open floating windows. Scrolls in a short dock |
| `SmarActTipTilt` (12), `SmarActEncodedTipTilt` (1) | 13 | `home_screen/screens/tip_tilt.py`, pcdswidgets' `MotorTipTiltDouble`: d-pad, step size and position per axis, invert, per-axis expert buttons. Tip (`{prefix}{tip_pv}`) is left/right, tilt is up/down, as in pcdsdevices' screen. Open-loop stages use the SmarAct step fields; the encoded one (`STYLE: MotorRecord`) its motor records |
| `EnvironmentalMonitor` | 4 | `home_screen/screens/env_monitor.ui` |
| `El3174AiCh` | 1 | `home_screen/screens/power_meter.ui` (the EJX power meter, an EL3174 analog-input channel): large `.VAL` readout with units, 5-minute trend, calibration fields (raw ADC, units, slope, offset, conversion, precision) |
| `EllRotation` (4), `Ell9` (2), `EllLinear` (1), `Ell6` (1) | 8 | `home_screen/screens/elliptec.py` + `elliptec.ui`, one screen for every Thorlabs Elliptec (thorlabs-ell IOC, PVs `{prefix}:M{channel}:...`): status, current position, move to, jog, jog step, home / optimize / clean / stop, position names, stage info. The `STAGE` macro (`continuous`, `ell6`, `ell9`) drops the sections whose records that stage type doesn't load (see the IOC's `st.cmd`). Scrolls in a short dock |

Every active class has a screen. A class without `screen:` in `home_screen/config/device_types.yaml` opens a placeholder (name, class, prefix, "no screen yet") and still has a status dot.

### Per-device happi kwargs

Tip/tilt stages and Elliptecs can't be described by `{prefix}` alone: their PVs depend on happi kwargs (`tip_pv: '{{ioc_tip_suffix}}'`, `channel: '{{ioc_channel}}'`, `port: '15'`). `devices.py` keeps each entry's kwargs, with the `{{field}}` templates filled in from the entry, and makes them available as `{tip_pv}`, `{channel}`, ... in `device_types.yaml`. For example, `LM1K4:OPA_MP1_MR1` with `tip_pv: _TIP1` gives `{prefix}{tip_pv}:STEP_COUNT` → `LM1K4:OPA_MP1_MR1_TIP1:STEP_COUNT`. `home_screen/tools/gen_indicator_pvs.py` builds such classes with the placeholders listed under `template_kwargs:`.

## Files

| Path | What it is |
|---|---|
| [`../home_screen/`](../home_screen/README.md) | The shared package: home screen, floor-plan code, every device screen, `home_screen/config/device_types.yaml` (device class → screen, macros, status PVs) and the tools (`gen_indicator_pvs.py`, `export_happi_devices.py`). |
| `floorplan.yaml` | **All layout and behaviour**: the drawing (stations left to right, relative widths/heights, colours, preferred height), station → location groups and tools, icon positions (percent of their station) and what each opens. Its `toolbar:` is the live `/cds/group/pcds/epics-dev/screens/pydm/lucid_config/IP1_MODS_toolbar.yaml`: a renamed button the floor plan refers to shows as "(missing)". Defaults (menu `functions`, colours) come from the package. Edit this to move or add things; no code changes needed. |
| `mods_ip1_home.py` | The home screen: the shared `home_screen/example/example_home.py`, opening this directory's `floorplan.yaml`. Production runs it directly with pydm. |
| `mods_ip1_home.sh` | Dev launcher: this location's `subnet_check` arguments, then `../home_screen/launch_home.sh mods_ip1_home.py` (ctrlenv-widgets, this checkout's pcdswidgets on `PYTHONPATH`). |
| `floorplan.png` | Screenshot of the floor plan (documentation only). |

## Config entry types (`opens:`)

```yaml
- device: lm1k4_inj_env_sens                                  # a happi device, via home_screen/config/device_types.yaml
- devices: {location: [6_lm1k4_ejx], function: [elliptecs]}   # all matching happi devices, as a sub-menu
- screen: env_monitor.ui                                      # any pydm screen in screens/ (or an absolute path)
  macros: {PREFIX: LM1K4:INJ_BHC_AI_01, NAME: inj}
  title: INJ T/H
- toolbar: [Tools, EJX non-LSS Shutter]                       # run a toolbar button's command (external)
- toolbar: [Tools, nf-ff-alignment, COM_DP1]                  # one command of a button with several titles
```

One entry means a click opens it directly; several mean a click shows a menu.

## Tests

This location has no tests of its own: the [home_screen](../home_screen/README.md#tests) package's core tests check every location's `floorplan.yaml` (references resolve, every happi device is in exactly one menu, status PVs are filled in, toolbar commands) against its toolbar and its happi snapshot, `home_screen/tests/snapshots/mods_ip1.yaml`.

## Known gaps / next steps

- **Spectrometer status dots watch big waveforms.** `QminiSpectrometer`'s generated `indicator_pvs` include `:SPECTRUM` and `:WAVELENGTHS` (the same signals typhos watched). They work, but each update is a full array; trimming them to `:STATUS` / `:W0_FIT` would be cheaper. `gen_indicator_pvs.py` would put them back on the next run, so this needs a small exclude option there first.
- **Station layout is schematic** (equal boxes in beam order), not the real table. Fine-tune widths, heights and icon positions in `floorplan.yaml`, or replace with a sketch of the table.
