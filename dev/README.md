# Home screens rebuilt with pcdswidgets (dev)

Home screens rebuilt from pcdswidgets and PyDM, with no runtime dependency on happi, ophyd, pcdsdevices, typhos or lucid. Each directory is standalone: it needs only PyDM and a pcdswidgets, and nothing from the other directories here.

| Directory | Replaces | Style | Run |
|---|---|---|---|
| [las](las/README.md) | `las` (LUCID), in the `lasdev` style | Clickable laser-hall floor plan (bays, racks R01–R20, BTS) + toolbar + TabDock | `dev/las/las_home.sh` |
| [mods_ip1](mods_ip1/README.md) | `mods_ip1` (LUCID, `IP1_MODS`, LM1K4) | Clickable IP1 MODS table (stations INJ → COM → OPA → HRM → ATM → EJX) + toolbar + TabDock | `dev/mods_ip1/mods_ip1_home.sh` |
| [mods_ip2](mods_ip2/README.md) | `mods_ip2` (LUCID, `IP2_MODS`, LM2K4) | Same as mods_ip1, IP2 table (INJ → COM → HRM → ATM → EJX) | `dev/mods_ip2/mods_ip2_home.sh` |
| [mods_qrix](mods_qrix/README.md) | `mods_qrix` (LUCID, `QRIX_MODS`, LM1K2) | Same as mods_ip1, QRIX table (INJ → COM → ATM → OPA → EJX) | `dev/mods_qrix/mods_qrix_home.sh` |
| [mods_crix](mods_crix/README.md) | `mods_crix` (LUCID, `CRIX_MODS`, LM2K2) | Same as mods_ip1, CRIX table (INJ → COM → ATM → HRM → EJX) | `dev/mods_crix/mods_crix_home.sh` |
| [v1](v1/README.md) | `las` (LUCID) | Earlier experiment: auto-generated device grid (location × function) + toolbar + TabDock | `dev/v1/las_home.sh` |

`las` and each `mods_*` directory have a `floorplan.png` screenshot of their floor plan.

The four `mods_*` directories share the same code and device screens (SmarAct, tip/tilt, camera, Qmini spectrometer, Elliptec, power meter, T/H). Only their config differs: `config/floorplan.yaml`, the toolbar copy, the happi snapshot, and the tests. The shared code and screens are copies, so a fix in one directory has to be copied to the others. mods_ip1 has been tested against live IOCs; mods_ip2, mods_qrix and mods_crix have so far only been checked offline.

## Making another one

`las` is the template for a new kind of screen. For another MODS hutch, start from the `mods_*` directory with the closest device set (e.g. `mods_crix` for power meters, `mods_qrix` for station tools with quoted commands):

1. Copy the directory, rename the launcher, the home module and the identifiers (beamline, toolbar file, device-DB environment variable, `subnet_check` arguments).
2. Copy the hutch's `lucid_config/<HUTCH>_toolbar.yaml` into `config/`, and write `config/floorplan.yaml` (the drawing, stations → happi location groups, station tools, icons only for functions that station has).
3. Check every active class has an entry in `config/device_types.yaml` (screen + macros; `template_kwargs` for classes built from happi kwargs). For a new class, add it and run `tools/gen_indicator_pvs.py` with the pcds conda python.
4. Run `tools/export_happi_devices.py <BEAMLINE> tests/devices_snapshot.yaml` and adapt the tests (device names, PVs, counts).

Each directory's README lists what its tests check.
