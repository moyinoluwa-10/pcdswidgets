# What happens when you type `las`

A trace of the LAS home screen launch, from the shell command to the LUCID window.
Traced on `psbuild-rocky9-01`, 2026-10-21. Paths and versions are as found on that date.

## Call chain

```
las                                  (bash function, /reg/g/pcds/setup/pcds_shortcuts.sh:395)
 ├─ subnet_check las las             (prints a read-only / write-enabled message)
 └─ $PYPS_SITE_TOP/config/las/las_home.sh &              (runs in background)
      └─ /reg/g/pcds/setup/lucid-launcher.sh LAS
           ├─ source /cds/group/pcds/pyps/conda/dev_conda    (Python environment)
           └─ lucid LAS --toolbar=$LUCID_CONFIG/LAS_toolbar.yaml &
                └─ python -m lucid → Qt window
```

## 1. Where `las` is defined

`las` is a bash function, not an executable on `PATH`. The shell picks it up at login:

```
~/.bashrc
 └─ /cds/group/pcds/engineering_tools/latest-released/scripts/ctrlenv_setup.sh
     └─ /cds/group/pcds/setup/epicsenv-cur.sh
         └─ /reg/g/pcds/setup/pcds_shortcuts.sh
```

```bash
las () {
    subnet_check las las
    "${PYPS_SITE_TOP}"/config/las/las_home.sh &
}
```

`PYPS_SITE_TOP=/reg/g/pcds/pyps`. `pcds_shortcuts.sh` defines the same kind of shortcut for every hutch.

## 2. `subnet_check`

When `pcds_shortcuts.sh` is sourced it:

1. Finds the host IP and sets `SUBNET` to the third octet. On a `255.255.252.0` (/22) network the low 2 bits are also set (`SUBNET | 3`).
2. Exports a subnet list for each hutch, e.g. `LAS_SUBNET=(160 161 162 163)`, `LASDEV_SUBNET=(12 13)`, `DEV_SUBNET=165`.

`subnet_check <screen> <subnet_name>...` checks whether `SUBNET` is in any of the named lists:

- match → `Warning: launching write-enabled LAS screen`
- no match → `Launching read-only LAS screen`

**The message is informational only.** It changes nothing about the screen. Write access is enforced on the EPICS side (channel access security and gateways, based on the client host/subnet). Example: `psbuild-rocky9-01` is on subnet 165 (DEV), so it gets the read-only message.

## 3. `las_home.sh`

`/reg/g/pcds/pyps/config/las/las_home.sh` is a template shared by several home screens (`mods_*_home.sh` and `timing_home.sh` are copies). It sets `HUTCH=las` and has one active option:

```bash
"${EPICS_SETUP}"/lucid-launcher.sh "${HUTCH^^}"     # ${HUTCH^^} → LAS
```

The other options are commented out:

- Option 3: LUCID from a pixi environment (`ctrlenv-lucid` / `ctrlenv-widget`)
- Option 4: a plain PyDM home screen, `pydm --hide-nav-bar ... las_home.ui` from `/cds/group/pcds/epics-dev/v1/screens/pydm/las`

Option 4 is the hook a pcdswidgets-based LAS screen would use.

## 4. `lucid-launcher.sh` and the conda environment

`/reg/g/pcds/setup/lucid-launcher.sh`:

```bash
source /cds/group/pcds/pyps/conda/dev_conda
# (UED-only PYTHONPATH override omitted)
lucid "$1" --toolbar="$LUCID_CONFIG"/"$1"_toolbar.yaml &
```

`dev_conda` sources `shared_conda_setup.sh` (from `engineering_tools/R4.6.0/scripts`), which:

- unsets `LD_LIBRARY_PATH` and `PYTHONPATH`
- sources `/reg/g/pcds/setup/epics-ca-env.sh`, which sets the Channel Access settings: `EPICS_CA_SERVER_PORT=5064`, `EPICS_CA_REPEATER_PORT=5065`, `EPICS_CA_MAX_ARRAY_BYTES=40000000`, `EPICS_CA_AUTO_ADDR_LIST=YES` (overridden per host for some consoles), connection timeout 30 s
- activates the env named in `py312/latest_env`, currently **`pcds-6.0.1`, Python 3.12**
- exports:
  - `LUCID_CONFIG=/cds/group/pcds/pyps/apps/hutch-python/lucid_config/`
  - `HAPPI_CFG=/cds/group/pcds/pyps/apps/hutch-python/device_config/happi.cfg`
  - `PYDM_DISPLAYS_PATH`, `PYDM_STYLESHEET` (vacuum `masterStyleSheet.qss`), `PYDM_DEFAULT_PROTOCOL=ca`
  - `QT_QUICK_BACKEND=software` over SSH

`dev_conda` then sets `PYTHONPATH=/cds/group/pcds/pyps/apps/dev/pythonpath`. That directory holds development checkouts (`lucid`, `pcdsdevices`, `pcdswidgets`, `atef`, ...), which load ahead of the installed versions. It also strips the installed `pcdsdevices` and `typhos` UI directories from `PYDM_DISPLAYS_PATH`, so the dev UI files are found first.

## 5. LUCID

Source: `/cds/group/pcds/pyps/apps/dev/pythonpath/lucid/` (symlink to `apps/dev/lucid/lucid`).

### `launcher.main()`

- sets ophyd `EpicsSignalBase` defaults: 10 s timeout and connection timeout
- `hacks.setup_rw_hack()`: on las-console, PVs sometimes disconnect and reconnect (roughly every 4 hours) without an access-rights update, which leaves widgets with no read/write access. The hack subscribes to each `EpicsSignal`'s metadata. On a connect without read access, it calls `pv.force_read_access_rights()` and re-runs the access callback.
- `launch(beamline=["LAS"], toolbar=...)`

### `launcher.launch()`

1. Creates the `QApplication` and shows the **splash screen**.
2. Builds `LucidMainWindow`:
   - **QuickAccessToolbar** (left), from `LAS_toolbar.yaml`
   - **IndicatorGrid** (centre), the device status grid
   - **LucidDock** (right), fixed 850 px wide; hidden when the window is too narrow ("Small window mode")
3. Installs PyDM's exception hook and optional centralized PCDS logging.
4. Starts **`HappiLoader`** (`QThread`):
   - `happi.Client.from_config()` → `device_config/db.json`
   - `cli.search(beamline="LAS", active=True)`
   - groups entries by `location_group` (rows) and `functional_group` (columns), as `"{row}|{col}"`
   - instantiates each entry as an ophyd device (`res.get(threaded=True)`) inside `typhos.utils.no_device_lazy_load()`
   - passes the groups to `window.grid.add_from_dict` on the GUI thread
5. When loading finishes, the splash closes and the window is shown.

From then on, widgets connect to IOC PVs over Channel Access via pyepics. Clicking a grid cell opens the device's **typhos** display in the dock.

### Toolbar YAML

`QuickAccessToolbar._button_factory` maps each entry's `type`:

| `type`    | Widget                        | Behaviour                          |
|-----------|-------------------------------|------------------------------------|
| `shell`   | `PyDMShellCommand`            | runs `commands`                    |
| `display` | `PyDMRelatedDisplayButton`    | opens `filename` (relative to the YAML) |
| `dock`    | `LucidDockButton`             | embeds a display in the dock       |

Other keys in the entry are set as Qt properties on the widget (e.g. `redirectCommandOutput`).

### Background processes

`las_home.sh &` and `lucid ... &` both run in the background. The prompt returns immediately, and LUCID's log lines (`[time] [LEVEL   ] - msg`) still print to that terminal.

## Baseline inventory (for a pcdswidgets rebuild)

### Toolbar: `LAS_toolbar.yaml`

68 active buttons (another 17 are commented out), **all `type: shell`**, in 10 tabs:
General, Bays 3/2, VNC, MODS, Laser Lockers, Event Timing, Timing, PDUs, SDG's, NEH Beam Transport.

Most buttons launch existing EDM/PyDM/standalone tools (iocmanager, StripTool, camviewer, LPS PLC screens, Qmini, SmarAct EDM, ...). None of them depend on happi, ophyd or typhos.
The 4 MODS buttons start separate LUCID instances for other hutches (`lucid-launcher.sh IP1_MODS`, ...).

### Grid: happi `beamline=LAS, active=True`

44 entries:

| `device_class`                                  | Count |
|-------------------------------------------------|------:|
| `pcdsdevices.areadetector.detectors.LasBasler`  | 20    |
| `pcdsdevices.epics_motor.SmarAct`               | 15    |
| `pcdsdevices.device_types.EnvironmentalMonitor` | 8     |
| `pcdsdevices.lasers.btps.BtpsState`             | 1     |

`location_group` (column headers): Bay 1, Bay 2, Bay 2 - 1um, Bay 2 - 800nm, Bay 3, Bay 4, Beam Transport
`functional_group` (row headers): BTPS, cameras, env sensors, smaract

These four device classes are the only grid dependency on happi, ophyd, pcdsdevices and typhos.

## Key files

| What | Path |
|------|------|
| Shortcut + subnet logic | `/reg/g/pcds/setup/pcds_shortcuts.sh` |
| LAS launcher | `/reg/g/pcds/pyps/config/las/las_home.sh` |
| LUCID launcher | `/reg/g/pcds/setup/lucid-launcher.sh` |
| Conda env setup | `/cds/group/pcds/pyps/conda/dev_conda` → `engineering_tools/R4.6.0/scripts/shared_conda_setup.sh` |
| CA env | `/reg/g/pcds/setup/epics-ca-env.sh` |
| LUCID source | `/cds/group/pcds/pyps/apps/dev/pythonpath/lucid/` |
| Toolbar config | `/cds/group/pcds/pyps/apps/hutch-python/lucid_config/LAS_toolbar.yaml` |
| happi config / db | `/cds/group/pcds/pyps/apps/hutch-python/device_config/{happi.cfg,db.json}` |
