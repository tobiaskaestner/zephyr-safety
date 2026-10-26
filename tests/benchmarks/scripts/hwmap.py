# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Read the hardware map of the host: which board is on which probe and console.

The file has the format of a twister hardware map, so twister makes it:

    west twister --generate-hardware-map hw-map.yml --persistent-hardware-map

Then set "platform" of each entry to the board target (as in boards.yaml)
and add the fixture "latbench_loopback" to each board that has the wire.
The file belongs to the host and is not checked in (.gitignore).
"""

from pathlib import Path

import yaml

BENCH_DIR = Path(__file__).resolve().parent.parent
DEFAULT = BENCH_DIR / "hw-map.yml"
SCHEMA = "scripts/schemas/twister/hwmap-schema.yaml"  # in a Zephyr tree
FIXTURE = "latbench_loopback"


class HwMapError(Exception):
    pass


def platforms(entry):
    """Return the board targets of an entry ("platform" is a string or a list)."""
    p = entry.get("platform")
    if isinstance(p, str):
        return p.split()
    if isinstance(p, list):
        return p
    return []


def fixture_names(entry):
    """Return the fixture names of an entry; "name:config" gives "name"."""
    return [f.split(":", 1)[0] for f in entry.get("fixtures") or []]


def load(path, schema_file=None):
    """Load a hardware map; check it against the twister schema if schema_file is given."""
    path = Path(path)
    if not path.is_file():
        raise HwMapError(
            f"no hardware map {path}; make it with 'west twister --generate-hardware-map {path.name}"
            " --persistent-hardware-map' (see the benchmark guide, host tools)"
        )
    entries = yaml.safe_load(path.read_text())
    if not isinstance(entries, list):
        raise HwMapError(f"{path}: a hardware map is a list of entries")
    if schema_file:
        import jsonschema

        schema = yaml.safe_load(Path(schema_file).read_text())
        try:
            jsonschema.validate(entries, schema)
        except jsonschema.ValidationError as e:
            where = "/".join(str(x) for x in e.absolute_path)
            raise HwMapError(f"{path}: {where}: {e.message} (schema {schema_file})") from None
    return entries


def select(entries, board, probe=None, path="hw-map"):
    """Return the one connected entry for board (and probe, if given)."""
    found = [e for e in entries if e.get("connected") and board in platforms(e)]
    if probe:
        found = [e for e in found if probe in (e.get("probe_id"), e.get("id"))]
    if not found:
        which = f"board '{board}'" + (f" and probe '{probe}'" if probe else "")
        raise HwMapError(f"{path}: no connected entry for {which}")
    if len(found) > 1:
        ids = [e.get("probe_id") or e.get("id") for e in found]
        raise HwMapError(f"{path}: {len(found)} connected entries for board '{board}' ({ids}); select one with --probe")
    entry = found[0]
    if not (entry.get("serial") or entry.get("serial_pty")):
        raise HwMapError(f"{path}: the entry for board '{board}' has no serial port")
    if entry.get("serial_pty"):
        raise HwMapError(f"{path}: the entry for board '{board}' has serial_pty; run.py reads a serial port only")
    if FIXTURE not in fixture_names(entry):
        raise HwMapError(
            f"{path}: the entry for board '{board}' has no fixture '{FIXTURE}'; add it when the board has the wire"
        )
    return entry


def hardware(entry):
    """Return the fields of an entry that a run uses and records."""
    return {
        "platform": platforms(entry),
        "probe": entry.get("probe_id") or entry["id"],
        "id": entry["id"],
        "product": entry.get("product"),
        "runner": entry.get("runner"),
        "serial": entry["serial"],
        "baud": entry.get("serial_baud") or entry.get("baud") or 115200,
        "fixtures": entry.get("fixtures") or [],
        "notes": entry.get("notes"),
    }
