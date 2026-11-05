# LAS home screen experiments (pcdswidgets dev)

Two takes on a LAS home screen built from pcdswidgets, with no runtime dependency on happi, ophyd, pcdsdevices, typhos or lucid.

| Version | Based on | Style | Run |
|---|---|---|---|
| [v1](v1/README.md) | `las` (LUCID) | Auto-generated device grid (location × function) + toolbar + TabDock | `dev/v1/las_home.sh` |
| [v2](v2/README.md) | `lasdev` (pydm home) | Clickable laser-hall floor plan + TabDock | `dev/v2/las_home.sh` |

v2 is standalone (it needs nothing from v1), so it can be copied as a template for other migrations.
