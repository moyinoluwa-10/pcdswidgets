# IP1 MODS (LM1K4) home screen

The `mods_ip1` home screen on the shared [home_screen](../home_screen/README.md) package: the IP1 MODS table, stations in beam order INJ → COM → OPA → HRM → ATM → EJX. How clicking, docking and status dots work: [Using a home screen](../home_screen/README.md#using-a-home-screen).

![floor plan](floorplan.png)

## Run it

```bash
pcdswidgets/dev/mods_ip1/mods_ip1_home.sh &                                 # dev
pydm --hide-nav-bar --hide-menu-bar --hide-status-bar mods_ip1_home.py      # production ("Option 4"), from this directory
```

It connects to the real IOCs. Today the `mods_ip1` shell function runs `subnet_check ip1 las tmo`, then `$PYPS_SITE_TOP/config/las/mods_ip1_home.sh`, which starts LUCID.

## What you can click

| Where | Opens |
|---|---|
| **Station** | Its devices by function (Cameras, SmarAct Motors, Spectrometers, Elliptecs, Power Meters, Temperature / Humidity), then its Tools. |
| **Cameras** / **SmarAct** / **Spectrometer** / **Elliptecs** / **Power** icons | That station's devices of that function. |
| **T/H** icons | That station's environmental sensor. |
| **Shutter** icons (ATM, EJX) | The toolbar's "ATM / EJX non-LSS Shutter", in its own window. No status dot. |

| Station | happi location groups | Tools |
|---|---|---|
| INJ | `1_lm1k4_inj` | WFS Expert Screen |
| COM | `2_lm1k4_com` | nf-ff-alignment (COM_DP1) |
| OPA | `3_lm1k4_opa` | |
| HRM | `3_lm1k4_hrm`, `4_lm1k4_hrm`, `4_lm1k4_int` | |
| ATM | `5_lm1k4_atm` | nf-ff-alignment (ATM_DP1), ATM non-LSS Shutter |
| EJX | `6_lm1k4_ejx` | EJX non-LSS Shutter |

## Devices

59 active devices (snapshot: `home_screen/tests/snapshots/mods_ip1.yaml`):

| Class | Count | Screen (`home_screen/screens/`) |
|---|---|---|
| `SmarAct` | 14 | `smaract.py` |
| `LasBasler` | 13 | `las_basler.ui` |
| `SmarActTipTilt`, `SmarActEncodedTipTilt` | 12 + 1 | `tip_tilt.py` |
| `EllRotation`, `Ell9`, `EllLinear`, `Ell6` | 4 + 2 + 1 + 1 | `elliptec.py` |
| `QminiSpectrometer` | 6 | `qmini.py` |
| `EnvironmentalMonitor` | 4 | `env_monitor.ui` |
| `El3174AiCh` | 1 | `power_meter.ui` |
