# What happens when you type `lasdev`

A trace of the LASDEV home screen launch, from the shell command to the window.
Traced 2026-10-22. Paths and versions are as found on that date.

**Short version:** unlike `las`, `lasdev` already runs a pcdswidgets home screen (no LUCID, no happi, no ophyd at runtime). It is a hand-built Designer `.ui`: a floor-plan image of the lab with camera buttons placed on it, which open camera screens in a `TabDock`. It runs from personal checkouts.

## Call chain

```
lasdev                                   (bash function, /reg/g/pcds/setup/pcds_shortcuts.sh:437)
 ├─ subnet_check lasdev lasdev           (read-only / write-enabled message; LASDEV_SUBNET=(12 13))
 └─ $PYPS_SITE_TOP/config/lasdev/lasdev_home.sh &
      ├─ source engineering_tools/latest-released/scripts/ctrlenv_setup.sh
      ├─ ctrlenv-pathmunge
      ├─ cd /cds/group/pcds/epics-dev/screens/pydm/lasdev
      └─ pixi run --as-is --manifest-path /cds/group/pcds/epics-dev/ipotanin/cam_widget_2 \
             pydm --hide-nav-bar --hide-menu-bar --hide-status-bar lasdev_home.ui
```

## 1. `lasdev` and `subnet_check`

These work the same way as for `las`: a bash function that calls `subnet_check`, which only prints a read-only or write-enabled message depending on the host's subnet, then starts the launcher in the background. `lasdev` is defined in `pcds_shortcuts.sh:437`, and the write-enabled subnets are `LASDEV_SUBNET=(12 13)`.

## 2. `lasdev_home.sh`

`/reg/g/pcds/pyps/config/lasdev/lasdev_home.sh` is the same template as `las_home.sh`, but it runs **Option 4 (pydm home)**. The active lines differ from the template:

- Instead of `ctrlenv-activate ctrlenv-widgets/...`, it runs PyDM through `pixi run --as-is --manifest-path /cds/group/pcds/epics-dev/ipotanin/cam_widget_2`.
  - `--as-is` uses that workspace's existing `.pixi` env as installed, without checking or updating the lock file.
- `lasdev_home.sh.bak` (Oct 15) is the earlier version, which used the shared `ctrlenv-widgets/latest-released` env. It was switched to the personal workspace the same day.

## 3. The Python environment: `ipotanin/cam_widget_2`

- A pcdswidgets clone (`github.com:ipotanin/pcdswidgets`) on branch **`pcdsImageView`**, with its own pixi workspace (same `pixi.toml` as upstream, plus `profile` extras and memray tasks).
- `pcdswidgets` is installed editable from that clone, so the screen runs whatever code is in that working tree.
- Default env: PyDM 1.29, with **no happi, ophyd, typhos or pcdsdevices installed**.
- Its `pcdswidgets/` package matches your checkout (`rodon007/pcdshub/pcdswidgets`), which already has `pcdsImageView` merged as PR #169. The only differences are `_version.py` and an extra `tests/tools`.
- The directory also holds about 800 MB of profiling output (`profile.bin`, `first_run_1cam_profile.bin`, memray HTML), and its own copy of `lasdev_home.ui`, identical to the one in `screens/pydm/lasdev`.

## 4. The home screen: `screens/pydm/lasdev/lasdev_home.ui`

Built in Designer from stock pcdswidgets widgets:

```
Form (1746 x 767)
├─ QTabWidget
│   ├─ "Camera/Motor" tab
│   │   └─ QFrame (800 x 700)
│   │       ├─ PyDMDrawingImage  asc_lab.png    (lab floor plan: lasers, MPC stages, beam paths, numbered points)
│   │       └─ 28 TabDockButtons placed on the image with absolute geometry (objectNames cam_1 ... cam_32, gaps)
│   └─ "Other" tab
│       └─ YamlToolbar  LASDEV_toolbar.yaml
└─ TabDock
```

There is no device grid, no happi lookup and no status indicators. Each button is a hard-coded `filename` + `macros` pair in the `.ui`.

### What the camera buttons open

| Buttons | Screen | Macros | Notes |
|---|---|---|---|
| cam_1–cam_5 | `ipotanin/laser_alignment_lock/laser_alignment_lock/screens/camera_view.py` | `config`, `devices` (paths into that repo's `dev-docs/`), `loop=CAM_n` | Camera + lock-loop controls; see §5 |
| cam_6, cam_7 ("IN"/"OUT") | `.../laser_alignment_lock/screens/simple_cam.ui` | `cam_prefix=LASDEV:CNT:CAM:06/07`, `horizontal_motor`/`vertical_motor` (picomotors `LASDEV:CNT:PIC:04:0x`, `PIC:05:0x`), `nickname` | Camera + tip/tilt |
| cam_29–cam_32 ("25"–"28") | `simple_cam.ui` | `cam_prefix=LASDEV:CNT:CAM:25..28`, motors `NA` | Test cameras, no motors |
| cam_8–cam_24 (17 buttons) | `test_cam.ui` (same dir) | none | **Placeholder:** `cam_prefix` is hard-coded to `LASDEV:CNT:CAM:01`, so all 17 open camera 01 |

### Toolbar: `LASDEV_toolbar.yaml`

One tab ("General") with 2 shell buttons. "TPR" and "PDU Rack 2" both run the same command, `.../ioc-lasdev-asc-tpr2/edm-ioc-lasdev-asc-tpr2.cmd`. "PDU Rack 2" is probably a copy-paste leftover.

## 5. Screens from `laser_alignment_lock`

`/cds/group/pcds/epics-dev/ipotanin/laser_alignment_lock` (`github.com:ipotanin/laser_alignment_lock`, branch **`oct-dev`**) is a beam-stabilization app. A caproto IOC (`LASDEV:LOCK:`) runs "LockLoops" that read camera centroids and step picomotors.

### `camera_view.py` (cam_1–5)

1. Adds its repo root to `sys.path` and imports `laser_alignment_lock.core.config`, which only needs the stdlib and `yaml`.
2. `build_macros(config, devices, loop)`:
   - reads `dev-docs/dev_config.yaml` (prefix `LASDEV:LOCK:`, loops `CAM_1`…`CAM_7`, each with X/Y axes naming an input camera and an output picomotor)
   - reads `dev-docs/dev_devices.json` with plain `json.load`. It is happi-format, but happi is not used. There are 92 entries: 24 `SimpleCameraStats` cameras (`LASDEV:CNT:CAM:01..`) and 68 `PicomotorAxis` (`LASDEV:CNT:PIC:01:01..`).
   - produces `LOOP_PREFIX`, `PX`, `PY`, `LOOP_NAME`, `cam_prefix`, `motor_x`, `motor_y`
3. Loads `camera_view.ui`, which contains:
   - `CameraViewerStretch` with the sidebar panels: Acquisition, Exposure, Centroid (`ROI1`), ROI, Markers, Colormap, a second ROI/Centroid pair on `ROI3`/`Stats3`, and `MotorTipTiltFull`
   - a `ViewSaver` (`~/.config/pcds_view_saves/view_saver_${LOOP_NAME}`)
   - a lock-loop status row: `${LOOP_PREFIX}STATUS`, `TASK_CMD`, `AVG_ERROR`, `INPUT_VALID`, `LAST_CORR_TS`, and per axis `ERROR_SIGNAL`, `INPUT_VALUE`, `TARGET_RBV`

The lock IOC is not in `config/lasdev/iocmanager.cfg`. It is started separately (`laser_alignment_lock/bin/ioc.py`), so the lock-loop row only works while someone is running it.

### `simple_cam.ui` (cam_6, 7, 25–28)

The same `CameraViewerStretch` sidebar (Centroid on `ROI1`), plus `MotorTipTiltFull` and `ViewSaver`, with no lock-loop row.

## 6. Other `config/lasdev` files

| File | Notes |
|---|---|
| `camviewer.cfg` | 5 cameras with different prefixes: `LASDEV:INJ_DP1_TF1_NF1/FF1`, `LASDEV:ASC:CAM:01..03`. They don't match the `LASDEV:CNT:CAM:*` used by the home screen. |
| `iocmanager.cfg` | 13 IOCs on `ctl-lasdev-asc-srv01..03`: gigECam (`cnt-cam-01`, `asc-cam-25`, `lm2k2-inj-gige-nf/ff-01`), picoMotion `pico-01..05`, TPR 1/2, PDU. Several are disabled. |
| `laser-alignment-lock/devices/` | Empty. |

## How `lasdev` compares with `las`

| | `las` | `lasdev` |
|---|---|---|
| Framework | LUCID (happi + ophyd + typhos) | pydm + pcdswidgets (already) |
| Env | shared `pcds-6.0.1` conda (`dev_conda`) | personal pixi workspace via `pixi run --as-is` |
| Device list | happi DB, 44 active LAS entries | hard-coded per button in the `.ui` (plus `dev_devices.json` for loops) |
| Layout | auto-generated grid (location × function) | hand-placed buttons on a floor-plan image |
| Status at a glance | alarm circle per device | none |
| Screens | typhos | pcdswidgets camera screens from `laser_alignment_lock` + a placeholder |
| Toolbar | 68 buttons / 10 tabs | 2 buttons / 1 tab |

## Fragile points of `lasdev` to keep in mind

- **Runs from personal checkouts.** The env (`ipotanin/cam_widget_2`, branch `pcdsImageView`) and the screens (`ipotanin/laser_alignment_lock`, branch `oct-dev`) are working trees. Any edit or branch switch there changes the production `lasdev` screen immediately.
- **`--as-is`.** The env is never re-resolved, so it can silently drift from its `pixi.lock`.
- **Absolute paths everywhere** in `lasdev_home.ui` (screen files and config files).
- **17 of 28 camera buttons are placeholders** that all show camera 01.
- **Device data is in three places that disagree:** `.ui` macros, `dev_devices.json`, and `camviewer.cfg`.
