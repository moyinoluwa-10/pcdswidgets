# home_screen: the floor-plan home screen package

One home screen for every location in the lasdev style (a drawing you click, the location's LUCID toolbar under it, a `TabDock` on the right): the laser hall ([las](../las/README.md)) and the MODS tables ([mods_ip1](../mods_ip1/README.md), [mods_ip2](../mods_ip2/README.md), [mods_qrix](../mods_qrix/README.md), [mods_crix](../mods_crix/README.md)).

Everything they share lives here: the code, every device screen, the default menu `functions`, and `config/device_types.yaml`, **the one source of truth for what each device class opens and which PVs its status dot watches**. A location is three small files:

```
<location>/
  <location>_home.py   the home screen: example/example_home.py, unchanged (finds this package in a parent directory)
  <location>_home.sh   dev launcher: its subnet_check arguments, then launch_home.sh with its <location>_home.py
  floorplan.yaml       beamline, title, toolbar (the live lucid_config file), the drawing and what each click opens
  README.md, floorplan.png
```

It has **no runtime dependency on happi, ophyd, pcdsdevices, typhos or lucid**. It needs PyDM and a pcdswidgets (the environment's, or this checkout's via `PYTHONPATH`).

**Start from [example/](example)**: `example_home.py`, `example_home.sh` and a `floorplan.yaml` that uses every option, with comments. It runs (`example/example_home.sh`).

## Run a location

```bash
pcdswidgets/dev/las/las_home.sh &      # dev: subnet_check, ctrlenv-widgets, this checkout's pcdswidgets, then pydm
# production (the org launcher's "Option 4"): after ctrlenv-activate, from the location's directory
pydm --hide-nav-bar --hide-menu-bar --hide-status-bar las_home.py
```

`<location>_home.py` sets the `FLOORPLAN` macro to the `floorplan.yaml` next to it. Other macros: `TOOLBAR` (default: the floorplan.yaml's `toolbar`), `DEVICE_DB` (happi JSON or YAML snapshot, default `$HOME_DEVICE_DB`, then happi's from `$HAPPI_CFG`). `launch_home.sh` activates `ctrlenv-widgets/v1.2.1` (`ENVVER`), puts this checkout's pcdswidgets (`PCDSWIDGETS_DIR`) on `PYTHONPATH`, runs `subnet_check $SUBNET_CHECK`, and starts pydm in the foreground. **It connects to the real IOCs.**

## floorplan.yaml

[example/floorplan.yaml](example/floorplan.yaml) documents every key. In short: `beamline`, `title`, `toolbar`; `hall.columns`, the drawing left to right (`station`, `bay`, `area`, `racks`, `gap`); `stations` / `bays` / `areas` / `shutters` / `racks`, what each area opens; `icons`, small icons in an area at `[x %, y %]`. Anything at its default is left out, so each location's file holds only what is particular to it.

`opens:` entries: `device: <happi name>`, `devices: {location: [...], function: [...]}` (a sub-menu), `shutter: <LSn>`, `screen: <file>` with `macros:` and `title:` (from `screens/` here, a `screens/` next to the location's floorplan.yaml, or an absolute path), `toolbar: [<tab>, <button>]` or `[<tab>, <button>, <title>]` (runs the toolbar button's command). One entry: a click opens it directly; several: a menu.

## Using a home screen

- **Areas** (stations, bays) open a menu of every control in them, by function, then their shutters and Tools (toolbar buttons). Groups have "Open All". **Icons** open their own entries: one entry directly, several as a menu.
- Opening follows the `TabDock` conventions: a click replaces the current tab, ctrl+click opens a new tab, shift+click a new window, a right click shows the options menu. Docked screens taller than the dock scroll. External tools (toolbar commands, EDM, marked ↗) open in their own window.
- Each icon has a status dot: the worst alarm (typhos colours) across the PVs of everything it opens. Hovering lists the PVs that aren't OK.
- The drawing keeps its proportions and scales with the window; below 75 % of `reference_height` icons drop their labels. The location's full toolbar is under it.
- A device class without a `screen:` in `config/device_types.yaml` opens a placeholder (name, class, prefix) and still has a status dot.

## Files

| Path | What it is |
|---|---|
| `example/` | A runnable example location (LAS devices): `example_home.py`, `example_home.sh`, and `floorplan.yaml` with every option explained. Copy it to make a location. |
| `__init__.py` | Makes `home_screen` a Python package: its modules import each other relatively, and a location's `<location>_home.py` puts the package's parent directory on `sys.path` and imports `home_screen.home`. |
| `home.py` | The home screen (`FloorPlanHome`): floor plan with the location's toolbar under it, an 850 px `TabDock` on the right. `location_home(floorplan)` gives the class a `<location>_home.py` opens (its `intelclass`). |
| `launch_home.sh` | Dev launcher (see above). |
| `config/functions.yaml` | happi functional_group → menu title and icon, in menu order, for every location; a floorplan.yaml's `functions:` adds to or overrides it. |
| `context.py` | `FloorPlanContext`: loads a location's floorplan.yaml, toolbar and happi devices, and turns each `opens:` entry, station, bay and rack into `Opener`s; rack ↔ toolbar button matching ("… (R07)") and the PDU prefix / outlet count from a button's EDM launch. No widgets: the core tests use it directly. |
| `openers.py` | `Opener` (something a click opens: a dockable screen, an external command, or a group), `run_command` (runs toolbar commands detached), `DockScreen` (docked screens scroll instead of growing the window). |
| `floorplan.py` | `FloorPlan` / `Hall`: the drawing, laid out from the floorplan.yaml's `hall`, with the icons placed on it. |
| `widgets.py` | `AreaButton` (a station, bay, area or rack) and `IconButton` (with its status dot), the menus they show (sub-menus per group with "Open All", TabDock options per screen, ↗ for external commands), and the icons for the names floorplan.yaml uses. |
| `devices.py` | Device list from happi's `db.json` read as plain JSON (`$HOME_DEVICE_DB`, or `$HAPPI_CFG`) or a YAML snapshot, with each entry's happi kwargs (`{{field}}` templates filled in) usable as `{tip_pv}`, `{channel}`, … in device_types.yaml; device types; the per-device screen cache. |
| `alarm.py` | `PVAlarmCircle`, the status dot: worst alarm across a list of PVs, in typhos's colours. |
| `config/device_types.yaml` | Device class → screen, macros, `template_kwargs` and status PVs, for every class at every location. The tests fail if a class active at any location is missing. |
| `screens/smaract.py` | SmarAct screen from the IOC release's own widgets (`common/smaract/R4.0.0/motorScreens`, the release `ioc-las-bts-mcs1` builds against): the expert panel with the advanced-controls tabs (Open-loop, Closed-loop, Diagnostics, Configuration) always shown under it. This is `smaract_expert_screen.py` without the collapsible section and without the PicoScale tab. It uses the release's generated widget classes, because loading `smaract_advanced_controls.ui` directly hits a circular import in that package. |
| `screens/las_basler.ui`, `screens/las_basler_settings.ui` | LasBasler camera viewer, and its sidebar settings panel: The "LAS Basler Settings" sidebar panel of `las_basler.ui` (manufacturer, sensor, data type, trigger, binning, user sets, reset), embedded there as a `PyDMEmbeddedDisplay` so it can be edited on its own. It inherits the parent's macros (`CAM`); open it alone with `pydm -m CAM=... las_basler_settings.ui`. The embedded display (`las_settings` in `las_basler.ui`) has a `minimumSize` width of 390, like the other sidebar panels, so it fits the sidebar's 410 px scroll area: a container's explicit minimum overrides its contents' size hint, so this, not the settings `.ui`'s own maximum, is what sets the panel's width. |
| `screens/env_monitor.ui` | EnvironmentalMonitor (temperature / humidity). |
| `screens/tip_tilt.py` | `screens/tip_tilt.py`, pcdswidgets' `MotorTipTiltDouble`: d-pad, step size and position per axis, invert, per-axis expert buttons. Tip (`{prefix}{tip_pv}`) is left/right, tilt is up/down, as in pcdsdevices' screen. Open-loop stages use the SmarAct step fields; the encoded one (`STYLE: MotorRecord`) its motor records |
| `screens/qmini.py` | `screens/qmini.py`, the IOC release's own embedded screen, what LUCID opens (`common/qmini/R3.1.1/qminiScreens/QminiSpectrometer.embedded.py`): spectrum and fit plot, single exposure, save spectrum; "Parameters" / "Fit Settings" open floating windows. Scrolls in a short dock |
| `screens/elliptec.py`, `screens/elliptec.ui` | `screens/elliptec.py` + `elliptec.ui`, one screen for every Thorlabs Elliptec (thorlabs-ell IOC, PVs `{prefix}:M{channel}:...`): status, current position, move to, jog, jog step, home / optimize / clean / stop, position names, stage info. The `STAGE` macro (`continuous`, `ell6`, `ell9`) drops the sections whose records that stage type doesn't load (see the IOC's `st.cmd`). Scrolls in a short dock |
| `screens/power_meter.ui` | `screens/power_meter.ui` (the EJX power meter, an EL3174 analog-input channel): large `.VAL` readout with units, 5-minute trend, calibration fields (raw ADC, units, slope, offset, conversion, precision) |
| `screens/laser_shutter.ui` | One laser source: LSS opened/closed/permission/request, entry valve, BTPS safe-to-open, destination, override, latched error + Acknowledge, user Open/Close. |
| `screens/pdu_tripplite.py` | TrippLite PDU (pdu_snmp IOC): the PyDM version of `pduScreens/TrippLite_24.edl` (common/pdu_snmp R3.3.6), with everything that screen has: PDU info (name and location editable), PDU details (inputs, outputs, outlets, groups, phases, circuits, breakers, heatsinks), input and output details (frequency, voltage, power, current with min/max), Global Control (All On / All Off / Reboot), and per outlet its ID, name (editable), status, control state, command and ramp option. Every power command asks for confirmation; the per-outlet command is On / Off / Cycle buttons next to the current command. Power buttons are coloured by what they do: green On / All On, red Off / All Off, yellow Cycle / Reboot. The header has the IOC heartbeat and an IOC button (EDM's `ioc_soft.edl`). Fits the dock's width. |
| `tools/gen_indicator_pvs.py` | **Dev-time only, uses ophyd** (run with the pcds conda python). Regenerates `indicator_pvs` in `config/device_types.yaml`. |
| `tools/export_happi_devices.py` | Writes a location's snapshot, `tests/snapshots/<location>.yaml`, from happi (`$HAPPI_CFG`, never `$HOME_DEVICE_DB`), sorted by name, e.g. `python dev/home_screen/tools/export_happi_devices.py IP2_MODS dev/home_screen/tests/snapshots/mods_ip2.yaml`. No happi import. |
| `tests/` | Core tests (66), no UI: device data and types (`test_devices.py`), every location's config and the example (`test_config.py`) and toolbar commands (`test_commands.py`). `tests/snapshots/<location>.yaml`: a dated snapshot of each location's active happi devices, used instead of happi. |

## Adding a location

1. Copy `example/` to `dev/<location>/` and rename the files `<location>_home.py`, `<location>_home.sh`. Leave the `.py` as it is.
2. In the `.sh`, set `SUBNET_CHECK` (as in the location's `pcds_shortcuts.sh` function) and the path to `launch_home.sh` (`$HERE/../home_screen/launch_home.sh`) and the `.py`.
3. Edit `floorplan.yaml`: `beamline`, `title`, `toolbar` (`/cds/group/pcds/epics-dev/screens/pydm/lucid_config/<HUTCH>_toolbar.yaml`), then the drawing. Delete the comments and anything at its default.
4. `python dev/home_screen/tools/export_happi_devices.py <BEAMLINE> dev/home_screen/tests/snapshots/<location>.yaml`: the tests pick up the new location by itself (any `dev/*/floorplan.yaml`).
5. Run the tests: if a class at the new location has no device type, add it to `config/device_types.yaml` (with a screen in `screens/` if it needs a new one) and run `tools/gen_indicator_pvs.py`.

To deploy, copy `home_screen/` once and each location's directory under it or next to it (e.g. `screens/pydm/las/home_screen/` and `screens/pydm/las/.../mods_qrix/`): `<location>_home.py` imports the nearest `home_screen` package in a parent directory.

## Adding or changing a device screen

Change it here once and every location picks it up. A new class goes in `config/device_types.yaml` (`screen`, `macros`, `template_kwargs`); then regenerate its `indicator_pvs` with `tools/gen_indicator_pvs.py`.

Some classes' PVs depend on happi kwargs, not only `{prefix}` (tip/tilt stages: `tip_pv: '{{ioc_tip_suffix}}'`; Elliptecs: `channel: '{{ioc_channel}}'`). `devices.py` keeps each entry's kwargs with the `{{field}}` templates filled in from the entry, as `{tip_pv}`, `{channel}`, ... in `device_types.yaml`: `LM1K2:COM_MP2_MR4` with `tip_pv: _TIP1` gives `{prefix}{tip_pv}:STEP_COUNT` → `LM1K2:COM_MP2_MR4_TIP1:STEP_COUNT`. `gen_indicator_pvs.py` builds such classes with the placeholders listed under `template_kwargs:`.

## Tests

```bash
cd pcdswidgets/dev/home_screen
PYTHONPATH=../.. /reg/g/pcds/pyps/pixi/ctrlenv-widgets/v1.2.1/src/rhel9-x86_64/.pixi/envs/default/bin/python -m pytest tests -q
```

Core tests only: no widget is created or shown (no Qt application or display needed), channel access is pointed at `127.0.0.1`, and `run_command` is replaced so nothing external is launched. Every location (each `dev/*/floorplan.yaml`) is checked against its toolbar and its happi snapshot:

- happi entries load and filter like `happi search` (beamline, active), happi kwargs are filled in, and the `{...}` templates fill macros and status PVs
- device_types.yaml: every screen is in `screens/`, and every class active at every location has an entry
- each floorplan.yaml names its beamline, title and toolbar; its hall columns and icons are consistent
- each location's `<location>_home.py` is the example's, and its `.sh` runs it through `launch_home.sh`
- the example opens only things that exist, and its `functions` add to the package's
- every device, screen and toolbar button a config names exists, and every icon opens something
- every active happi device is in exactly one area's menu (the LAS BTPS: the toolbar instead), and status PVs are filled in
- with a happi JSON database only the floorplan.yaml's beamline is loaded
- toolbar commands: multi-command buttons split by title, quoted arguments stay whole, the LAS racks open their PDU's screen with the prefix from its EDM launch

## Known gaps

- **Spectrometer status dots watch big waveforms.** `QminiSpectrometer`'s `indicator_pvs` include `:SPECTRUM` and `:WAVELENGTHS` (what typhos watched): every update is a full array. `:STATUS` / `:W0_FIT` would be cheaper, but `gen_indicator_pvs.py` needs an exclude option first, or it puts them back.
