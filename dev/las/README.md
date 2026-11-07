# LAS home screen (lasdev style)

The `las` home screen on the shared [home_screen](../home_screen/README.md) package: a drawing of the laser hall (Bays 1–4, racks R01–R20, BTS). How clicking, docking and status dots work: [Using a home screen](../home_screen/README.md#using-a-home-screen). How `lasdev` works today: [lasdev_launch_internals.md](lasdev_launch_internals.md).

![floor plan](floorplan.png)

## Run it

```bash
pcdswidgets/dev/las/las_home.sh &                                           # dev
pydm --hide-nav-bar --hide-menu-bar --hide-status-bar las_home.py           # production ("Option 4"), from this directory
```

It connects to the real IOCs. Today the `las` shell function runs `subnet_check las las`, then `$PYPS_SITE_TOP/config/las/las_home.sh`, which starts LUCID.

## What you can click

| Where | Opens |
|---|---|
| **Bay 1–4** | Its devices by function (Cameras, SmarAct Motors, Temperature / Humidity), then Shutters, then Tools (Bays 2 and 3: their "Bays 3/2" toolbar buttons). "Bay 2 - 1um" and "Bay 2 - 800nm" count as Bay 2. |
| **BTS** | BTS cameras, and the toolbar's BTPS Overview, BTMS Overview, Laser Hall Vacuum, Shutters, BTS motors, RGA and QPCs (one entry per IOC). |
| **Racks** with a plug badge (R01, R03, R06, R07, R08, R13, R18) | The PDU in `pdu_tripplite.py`, in the dock. See below. |
| Grey racks | Tooltip only: no PDU button names them yet. |
| **T/H** icons | That environmental sensor. |
| **Cameras** / **SmarAct** icons | That bay's cameras or motors. |
| **Shutters** icons | The laser-source shutter screen: LS1 in Bay 1, LS3/LS4 in Bay 2, LS5/LS6 in Bay 3, LS8 in Bay 4. |
| **BTPS** icon | Runs the toolbar's "BTPS Overview" (the btms-ui screen, in its own window). No status dot. |

**Racks → PDUs.** A rack opens each button in the LAS toolbar's "PDUs" tab whose name ends with the rack, e.g. "Zone 1 TiSaph PSU/Chiller PDU (R07)". A TrippLite PDU opens `pdu_tripplite.py` with the PV prefix and outlet count of that button's EDM launch (`-m PRE=...`, `TrippLite_24.edl`, from the command or the `edm-ioc-*.cmd` script it runs); any other button runs its command. Add a button named "... (R12)" and R12 lights up. A rack can override this with its own `opens:` (`racks:` in `floorplan.yaml`).

## Devices

44 active devices (snapshot: `home_screen/tests/snapshots/las.yaml`):

| Class | Count | Screen (`home_screen/screens/`) |
|---|---|---|
| `LasBasler` | 20 | `las_basler.ui` |
| `SmarAct` | 15 | `smaract.py` |
| `EnvironmentalMonitor` | 8 | `env_monitor.ui` |
| `BtpsState` | 1 | none: the BTPS icon runs the toolbar's "BTPS Overview" |

Shutters use `laser_shutter.ui` (PVs `LTLHN:LSn:LST:*`, `LTLHN:LSn:BTPS:*`, as in `pcdsdevices.lasers.btps`); laser source → bay comes from the BTPS screen's tab names.
