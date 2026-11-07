# Home screens rebuilt with pcdswidgets (dev)

Home screens rebuilt from pcdswidgets and PyDM, with no runtime dependency on happi, ophyd, pcdsdevices, typhos or lucid. They need only PyDM and a pcdswidgets.

The floor-plan screens (`las` and the `mods_*` hutches) are **one package, [home_screen](home_screen/README.md)**, plus a small directory per location. The package has the code, every device screen, the tools, and `config/device_types.yaml`, the one source of truth for what each device class opens and which PVs its status dot watches. A location directory is only `floorplan.yaml` (the drawing, what each click opens, its happi `beamline`, window `title` and live `toolbar`), `<location>_home.py` (the same few lines everywhere) and a dev launcher `<location>_home.sh`. [home_screen/example](home_screen/example) is a runnable example with every option explained.

| Directory | Replaces | Style | Run |
|---|---|---|---|
| [home_screen](home_screen/README.md) | (shared) | The floor-plan home screen package: code, screens, device types, tools, generic launcher | via a location below |
| [las](las/README.md) | `las` (LUCID), in the `lasdev` style | Clickable laser-hall floor plan (bays, racks R01–R20, BTS) + toolbar + TabDock | `dev/las/las_home.sh` |
| [mods_ip1](mods_ip1/README.md) | `mods_ip1` (LUCID, `IP1_MODS`, LM1K4) | Clickable IP1 MODS table (stations INJ → COM → OPA → HRM → ATM → EJX) + toolbar + TabDock | `dev/mods_ip1/mods_ip1_home.sh` |
| [mods_ip2](mods_ip2/README.md) | `mods_ip2` (LUCID, `IP2_MODS`, LM2K4) | IP2 table (INJ → COM → HRM → ATM → EJX) | `dev/mods_ip2/mods_ip2_home.sh` |
| [mods_qrix](mods_qrix/README.md) | `mods_qrix` (LUCID, `QRIX_MODS`, LM1K2) | QRIX table (INJ → COM → ATM → OPA → EJX) | `dev/mods_qrix/mods_qrix_home.sh` |
| [mods_crix](mods_crix/README.md) | `mods_crix` (LUCID, `CRIX_MODS`, LM2K2) | CRIX table (INJ → COM → ATM → HRM → EJX) | `dev/mods_crix/mods_crix_home.sh` |
| [v1](v1/README.md) | `las` (LUCID), in LUCID's own style | LUCID look-alike: auto-generated device grid (location × function) + toolbar + TabDock. Standalone (its own copies of the device code and screens) | `dev/v1/las_home.sh` |

Each location has a `floorplan.png` screenshot of its floor plan; `v1` has `grid.png`, its device grid. All five floor-plan locations have been tested against live IOCs.

## Making another one

See [home_screen: Adding a location](home_screen/README.md#adding-a-location): copy [home_screen/example](home_screen/example) to `dev/<location>/`, rename its files, set the `.sh`'s `subnet_check` arguments, trim the `floorplan.yaml` to the location, and add a happi snapshot in `home_screen/tests/snapshots/`. A device class that no location had yet goes in `home_screen/config/device_types.yaml` (and its screen in `home_screen/screens/`), once, for everyone.

The [home_screen tests](home_screen/README.md#tests) are core tests (no UI) and check every location.
