# Home screens rebuilt with pcdswidgets (dev)

Home screens rebuilt from pcdswidgets and PyDM, with no runtime dependency on happi, ophyd, pcdsdevices, typhos or lucid. Each directory is standalone: it needs only PyDM and a pcdswidgets, and nothing from the other directories here.

| Directory | Replaces | Style | Run |
|---|---|---|---|
| [las](las/README.md) | `las` (LUCID), in the `lasdev` style | Clickable laser-hall floor plan (bays, racks R01–R20, BTS) + toolbar + TabDock | `dev/las/las_home.sh` |
| [mods_ip1](mods_ip1/README.md) | `mods_ip1` (LUCID, `IP1_MODS`) | Clickable IP1 MODS table (stations INJ → EJX in beam order) + toolbar + TabDock | `dev/mods_ip1/mods_ip1_home.sh` |
| [v1](v1/README.md) | `las` (LUCID) | Earlier experiment: auto-generated device grid (location × function) + toolbar + TabDock | `dev/v1/las_home.sh` |

## Making another one

`las` is the template; `mods_ip1` was made from it. To migrate another LUCID home screen:

1. Copy `las/` to a new directory, rename the launcher and home module, and set the beamline, toolbar file and device-DB environment variable.
2. Copy the hutch's `lucid_config/<HUTCH>_toolbar.yaml` into `config/`, and write `config/floorplan.yaml` (the drawing, areas → happi location groups, icons).
3. List the device classes in `config/device_types.yaml` (screen + macros where one exists; `template_kwargs` for classes built from happi kwargs), then run `tools/gen_indicator_pvs.py` with the pcds conda python.
4. Run `tools/export_happi_devices.py <BEAMLINE> tests/devices_snapshot.yaml` and adapt the tests.

Both READMEs list what each directory's tests check.
