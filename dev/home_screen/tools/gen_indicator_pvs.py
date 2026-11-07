"""
Regenerate the ``indicator_pvs`` lists in config/device_types.yaml.

This is a development-time tool and the only place in dev/home_screen that imports ophyd and pcdsdevices.
The runtime screens only read the YAML this writes.

LUCID's grid uses a TyphosAlarmCircle per device, which watches the device's
hinted signals if it has any, otherwise its hinted + normal signals.
We reproduce that selection here so the PV-only indicator watches the same PVs.
Non-EPICS signals are skipped: typhos registers them as local signals that are
always connected with no alarm, so they never change the summary color.

Usage (with the shared pcds conda python, nothing is installed or modified)::

    python dev/home_screen/tools/gen_indicator_pvs.py            # rewrite config/device_types.yaml
    python dev/home_screen/tools/gen_indicator_pvs.py --dry-run  # print counts only
"""

import argparse
import importlib
import os
import warnings
from pathlib import Path

import yaml

TYPES_FILE = Path(__file__).resolve().parent.parent / "config" / "device_types.yaml"

# Building the template devices creates channels for names like "{prefix}Acquire"; keep their searches local
os.environ.update(EPICS_CA_AUTO_ADDR_LIST="NO", EPICS_CA_ADDR_LIST="127.0.0.1")

# ophyd concatenates the prefix with each suffix, so building the device with a
# literal "{prefix}" gives PV names that are templates for any instance.
PREFIX_TEMPLATE = "{prefix}"


def indicator_pvs_for_class(device_class: str, template_kwargs: list[str] | None = None) -> list[str]:
    from ophyd import Kind
    from ophyd.signal import EpicsSignalBase

    module_name, class_name = device_class.rsplit(".", 1)
    cls = getattr(importlib.import_module(module_name), class_name)
    # Per-instance happi kwargs (e.g. tip_pv, channel) become "{tip_pv}" templates, filled in per device at runtime
    kwargs = {key: "{" + key + "}" for key in template_kwargs or []}
    try:
        device = cls(PREFIX_TEMPLATE, name="template", **kwargs)
    except TypeError:
        device = cls(name="template", **kwargs)
    hints = device.hints.get("fields", [])
    kinds = (Kind.hinted,) if hints else (Kind.hinted, Kind.normal)
    pvs = []
    for walk in device.walk_signals(include_lazy=True):
        sig = walk.item
        if sig.kind not in kinds or not isinstance(sig, EpicsSignalBase):
            continue
        pvs.append(sig.pvname)
    return sorted(set(pvs))


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--types-file", default=str(TYPES_FILE))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    warnings.simplefilter("ignore")
    with open(args.types_file) as fd:
        text = fd.read()
    types = yaml.safe_load(text)
    # Keep the file's own leading comment block when rewriting it
    header = ""
    for line in text.splitlines():
        if not line.startswith("#"):
            break
        header += line + "\n"

    for device_class, cfg in types.items():
        try:
            pvs = indicator_pvs_for_class(device_class, cfg.get("template_kwargs"))
        except Exception as ex:
            print(f"{device_class}: FAILED, keeping the old list ({type(ex).__name__}: {ex})")
            continue
        print(f"{device_class}: {len(pvs)} indicator PVs")
        cfg["indicator_pvs"] = pvs

    if not args.dry_run:
        with open(args.types_file, "w") as fd:
            fd.write(header)
            yaml.safe_dump(types, fd, sort_keys=False, width=120)
        print(f"Wrote {args.types_file}")


if __name__ == "__main__":
    main()
