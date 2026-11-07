# CRIX MODS (LM2K2) home screen

The `mods_crix` home screen on the shared [home_screen](../home_screen/README.md) package: the CRIX MODS table, stations in beam order INJ → COM → ATM → HRM → EJX. How clicking, docking and status dots work: [Using a home screen](../home_screen/README.md#using-a-home-screen).

![floor plan](floorplan.png)

## Run it

```bash
pcdswidgets/dev/mods_crix/mods_crix_home.sh &                               # dev
pydm --hide-nav-bar --hide-menu-bar --hide-status-bar mods_crix_home.py     # production ("Option 4"), from this directory
```

It connects to the real IOCs. Today the `mods_crix` shell function runs `subnet_check crix las rix`, then `$PYPS_SITE_TOP/config/las/mods_crix_home.sh`, which starts LUCID.

## What you can click

| Where | Opens |
|---|---|
| **Station** | Its devices by function (Cameras, SmarAct Motors, Spectrometers, Elliptecs, Power Meters, Temperature / Humidity). |
| **Cameras** / **SmarAct** / **Spectrometer** / **Elliptecs** / **Power** icons | That station's devices of that function. |
| **T/H** icons | That station's environmental sensor. |

| Station | happi location group |
|---|---|
| INJ | `1_lm2k2_inj` |
| COM | `2_lm2k2_com` |
| ATM | `3_lm2k2_atm` |
| HRM | `4_lm2k2_hrm` |
| EJX | `5_lm2k2_ejx` |

No station has tools: no CRIX_MODS toolbar button belongs to one station, so every button is only in the toolbar. There are no shutters in the toolbar, so no shutter icons.

## Devices

76 active devices (snapshot: `home_screen/tests/snapshots/mods_crix.yaml`):

| Class | Count | Screen (`home_screen/screens/`) |
|---|---|---|
| `SmarAct` | 23 | `smaract.py` |
| `SmarActTipTilt`, `SmarActEncodedTipTilt` | 14 + 1 | `tip_tilt.py` |
| `LasBasler` | 15 | `las_basler.ui` |
| `EllRotation`, `EllLinear`, `Ell6` | 5 + 3 + 2 | `elliptec.py` |
| `EnvironmentalMonitor` | 5 | `env_monitor.ui` |
| `El3174AiCh` | 5 | `power_meter.ui` |
| `QminiSpectrometer` | 3 | `qmini.py` |
