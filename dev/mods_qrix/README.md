# QRIX MODS (LM1K2) home screen

The `mods_qrix` home screen on the shared [home_screen](../home_screen/README.md) package: the QRIX MODS table, stations in beam order INJ → COM → ATM → OPA → EJX. How clicking, docking and status dots work: [Using a home screen](../home_screen/README.md#using-a-home-screen).

![floor plan](floorplan.png)

## Run it

```bash
pcdswidgets/dev/mods_qrix/mods_qrix_home.sh &                               # dev
pydm --hide-nav-bar --hide-menu-bar --hide-status-bar mods_qrix_home.py     # production ("Option 4"), from this directory
```

It connects to the real IOCs. Today the `mods_qrix` shell function runs `subnet_check qrix las rix`, then `$PYPS_SITE_TOP/config/las/mods_qrix_home.sh`, which starts LUCID.

## What you can click

| Where | Opens |
|---|---|
| **Station** | Its devices by function (Cameras, SmarAct Motors, Spectrometers, Elliptecs), then its Tools. |
| **Cameras** / **SmarAct** / **Spectrometer** / **Elliptecs** icons | That station's devices of that function. |

| Station | happi location group | Tools |
|---|---|---|
| INJ | `1_lm1k2_inj` | |
| COM | `2_lm1k2_com` | |
| ATM | `3_lm1k2_atm` | Dispersion Scan ATM |
| OPA | `4_lm1k2_opa` | THz 1D-scan |
| EJX | `5_lm1k2_ejx` | |

QRIX_MODS has no environmental sensors in happi and no shutters, so there are no T/H or shutter icons. Every other toolbar button is only in the toolbar.

## Devices

42 active devices (snapshot: `home_screen/tests/snapshots/mods_qrix.yaml`):

| Class | Count | Screen (`home_screen/screens/`) |
|---|---|---|
| `SmarAct` | 13 | `smaract.py` |
| `SmarActEncodedTipTilt`, `SmarActTipTilt` | 7 + 4 | `tip_tilt.py` |
| `EllRotation`, `EllLinear`, `Ell9` | 5 + 4 + 1 | `elliptec.py` |
| `LasBasler` | 6 | `las_basler.ui` |
| `QminiSpectrometer` | 2 | `qmini.py` |
