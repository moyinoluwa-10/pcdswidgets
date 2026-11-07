# Home screens rebuilt with pcdswidgets (dev)

Home screens rebuilt from pcdswidgets and PyDM, with no runtime dependency on happi, ophyd, pcdsdevices, typhos or lucid. They need only PyDM and a pcdswidgets.

The floor-plan screens (`las` and the `mods_*` hutches) are **one package, [home_screen](home_screen/README.md)**, plus a small directory per location. The package has the code, every device screen, the tools, and `config/device_types.yaml`, the one source of truth for what each device class opens and which PVs its status dot watches. A location directory is only its launcher, `config/floorplan.yaml` (the drawing, what each click opens, its happi `beamline`, window `title` and `toolbar`), its toolbar copy, and its tests.

| Directory | Replaces | Style | Run |
|---|---|---|---|
| [home_screen](home_screen/README.md) | (shared) | The floor-plan home screen package: code, screens, device types, tools, generic launcher | via a location below |
| [las](las/README.md) | `las` (LUCID), in the `lasdev` style | Clickable laser-hall floor plan (bays, racks R01–R20, BTS) + toolbar + TabDock | `dev/las/las_home.sh` |
| [mods_ip1](mods_ip1/README.md) | `mods_ip1` (LUCID, `IP1_MODS`, LM1K4) | Clickable IP1 MODS table (stations INJ → COM → OPA → HRM → ATM → EJX) + toolbar + TabDock | `dev/mods_ip1/mods_ip1_home.sh` |
| [mods_ip2](mods_ip2/README.md) | `mods_ip2` (LUCID, `IP2_MODS`, LM2K4) | IP2 table (INJ → COM → HRM → ATM → EJX) | `dev/mods_ip2/mods_ip2_home.sh` |
| [mods_qrix](mods_qrix/README.md) | `mods_qrix` (LUCID, `QRIX_MODS`, LM1K2) | QRIX table (INJ → COM → ATM → OPA → EJX) | `dev/mods_qrix/mods_qrix_home.sh` |
| [mods_crix](mods_crix/README.md) | `mods_crix` (LUCID, `CRIX_MODS`, LM2K2) | CRIX table (INJ → COM → ATM → HRM → EJX) | `dev/mods_crix/mods_crix_home.sh` |
| [v1](v1/README.md) | `las` (LUCID), in LUCID's own style | LUCID look-alike: auto-generated device grid (location × function) + toolbar + TabDock. Standalone (its own copies of the device code and screens) | `dev/v1/las_home.sh` |

Each location has a `floorplan.png` screenshot of its floor plan; `v1` has `grid.png`, its device grid. mods_ip1 has been tested against live IOCs; mods_ip2, mods_qrix and mods_crix have so far only been checked offline.

## Making another one

See [home_screen: Adding a location](home_screen/README.md#adding-a-location): a new `dev/<location>/` with its `config/floorplan.yaml` (start from the location with the closest layout), its toolbar copy, a launcher with its `subnet_check` arguments, a happi snapshot and tests. A device class that no location had yet goes in `home_screen/config/device_types.yaml` (and its screen in `home_screen/screens/`), once, for everyone.

Each directory's README lists what its tests check.
