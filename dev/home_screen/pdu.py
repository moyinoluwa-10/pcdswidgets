"""Rack and PDU matching: which toolbar buttons belong to a rack, and the PDU macros their EDM launch uses."""

import logging
import os
import re
import shlex
from pathlib import Path

logger = logging.getLogger(__name__)

# "Zone 1 TiSaph PSU/Chiller PDU (R07)" -> R07
RACK_IN_NAME = re.compile(r"\((R\d+)\)")
# A TrippLite PDU's EDM launch: its PV prefix and outlet count, from the toolbar command or the .cmd script it runs
PDU_PRE = re.compile(r"PRE=([A-Za-z0-9:_-]+)")
PDU_IOC = re.compile(r"IOC=([A-Za-z0-9:_-]+)")
PDU_EDL = re.compile(r"TrippLite_(\d+)\.edl")


def pdu_macros(commands: list[str]) -> dict[str, str] | None:
    """{"PRE": ..., "N_CHAN": ..., "IOC": ...} for a TrippLite PDU's EDM launch commands, or None if they aren't one."""
    for command in commands:
        texts = [command]
        script = Path(os.path.expanduser(shlex.split(command)[0])) if command.strip() else None
        if script is not None and script.suffix == ".cmd" and script.is_file():
            try:
                texts.append(script.read_text(errors="replace"))
            except OSError:
                logger.debug("Could not read %s", script, exc_info=True)
        for text in texts:
            # Only lines that aren't comments: the toolbar and the .cmd scripts keep old launches commented out
            text = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
            pre, edl = PDU_PRE.search(text), PDU_EDL.search(text)
            if pre and edl:
                macros = {"PRE": pre.group(1), "N_CHAN": edl.group(1)}
                if ioc := PDU_IOC.search(text):
                    macros["IOC"] = ioc.group(1)
                return macros
    return None
