# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the hardware map (scripts/hwmap.py) and its use in run.py (no board)."""

import argparse
import sys
from pathlib import Path

import pytest
import yaml

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

import hwmap  # noqa: E402
import run  # noqa: E402
import trees  # noqa: E402

G4 = {
    "connected": True,
    "id": "0042003F3433510A37363934",
    "platform": "nucleo_g474re",
    "product": "STLINK-V3",
    "runner": "openocd",
    "serial": "/dev/serial/by-id/usb-STMicroelectronics_STLINK-V3_0042003F3433510A37363934-if02",
    "fixtures": ["latbench_loopback:D2-A3"],
}
NRF = {
    "connected": True,
    "id": "001057794158",
    "platform": ["nrf54l15dk/nrf54l15/cpuapp"],
    "product": "J-Link",
    "runner": "jlink",
    "serial": "/dev/serial/by-id/usb-SEGGER_J-Link_001057794158-if02",
    "fixtures": ["latbench_loopback"],
}

# The required keys and a few properties of the twister schema, for tests
# without a Zephyr tree.
SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {k: {"type": "string"} for k in ("id", "product", "runner", "serial", "probe_id", "notes")}
        | {"connected": {"type": "boolean"}, "platform": {}, "baud": {"type": "integer"},
           "fixtures": {"type": "array", "items": {"type": "string"}}},
        "required": ["connected", "id", "platform", "product", "runner"],
        "additionalProperties": False,
    },
}


def write(tmp_path, entries, name="hw-map.yml"):
    f = tmp_path / name
    f.write_text(yaml.safe_dump(entries))
    return f


def schema(tmp_path):
    f = tmp_path / "hwmap-schema.yaml"
    f.write_text(yaml.safe_dump(SCHEMA))
    return f


def test_load_and_select(tmp_path):
    entries = hwmap.load(write(tmp_path, [G4, NRF]), schema(tmp_path))
    hw = hwmap.hardware(hwmap.select(entries, "nucleo_g474re"))
    assert hw["probe"] == G4["id"]
    assert hw["serial"] == G4["serial"]
    assert hw["baud"] == 115200
    assert hwmap.select(entries, "nrf54l15dk/nrf54l15/cpuapp")["id"] == NRF["id"]


def test_load_missing_file(tmp_path):
    with pytest.raises(hwmap.HwMapError, match="generate-hardware-map"):
        hwmap.load(tmp_path / "hw-map.yml")


def test_load_rejects_unknown_key(tmp_path):
    with pytest.raises(hwmap.HwMapError, match="console"):
        hwmap.load(write(tmp_path, [G4 | {"console": "/dev/ttyACM0"}]), schema(tmp_path))


def test_load_rejects_missing_key(tmp_path):
    bad = {k: v for k, v in G4.items() if k != "runner"}
    with pytest.raises(hwmap.HwMapError, match="runner"):
        hwmap.load(write(tmp_path, [bad]), schema(tmp_path))


def test_platform_string_with_two_targets():
    e = G4 | {"platform": "nucleo_g474re other/board"}
    assert hwmap.platforms(e) == ["nucleo_g474re", "other/board"]
    assert hwmap.select([e], "other/board") is e


def test_probe_id_overrides_id():
    hw = hwmap.hardware(G4 | {"probe_id": "000609301751"})
    assert hw["probe"] == "000609301751"
    assert hw["id"] == G4["id"]


@pytest.mark.parametrize("entries, board, probe, match", [
    ([G4 | {"connected": False}], "nucleo_g474re", None, "no connected entry"),
    ([G4], "nrf54l15dk/nrf54l15/cpuapp", None, "no connected entry"),
    ([G4, G4 | {"id": "X"}], "nucleo_g474re", None, "select one with --probe"),
    ([G4], "nucleo_g474re", "X", "and probe 'X'"),
    ([G4 | {"fixtures": []}], "nucleo_g474re", None, "latbench_loopback"),
    ([G4 | {"fixtures": ["gpio_loopback"]}], "nucleo_g474re", None, "latbench_loopback"),
    ([G4 | {"serial": None}], "nucleo_g474re", None, "no serial port"),
    ([G4 | {"serial_pty": "x.py"}], "nucleo_g474re", None, "serial_pty"),
])
def test_select_errors(entries, board, probe, match):
    with pytest.raises(hwmap.HwMapError, match=match):
        hwmap.select(entries, board, probe)


def test_select_with_probe_among_two():
    other = G4 | {"id": "X"}
    assert hwmap.select([G4, other], "nucleo_g474re", "X") is other


def test_select_hardware_from_map(tmp_path):
    zephyr = tmp_path / "zephyr"
    (zephyr / Path(hwmap.SCHEMA).parent).mkdir(parents=True)
    (zephyr / hwmap.SCHEMA).write_text(yaml.safe_dump(SCHEMA))
    args = argparse.Namespace(hardware_map=str(write(tmp_path, [G4])), probe=None, port=None)
    hw = run.select_hardware(args, "nucleo_g474re", zephyr)
    assert hw["probe"] == G4["id"]
    assert hw["map"] == str((tmp_path / "hw-map.yml").resolve())
    args.port = "/dev/serial/by-id/other"
    assert run.select_hardware(args, "nucleo_g474re", zephyr)["serial"] == "/dev/serial/by-id/other"


def test_select_hardware_without_map(tmp_path):
    args = argparse.Namespace(hardware_map=str(tmp_path / "none.yml"), probe="P", port="/dev/x")
    hw = run.select_hardware(args, "nucleo_g474re", tmp_path)
    assert (hw["probe"], hw["serial"]) == ("P", "/dev/x")
    args.probe = None
    with pytest.raises(SystemExit, match="no hardware map"):
        run.select_hardware(args, "nucleo_g474re", tmp_path)


def test_flash_commands_name_the_probe(tmp_path):
    """Each board selects its probe; no flash command may work on any probe."""
    boards = trees.load_boards()
    for name, cfg in boards["boards"].items():
        cmd = run.flash_command(cfg, tmp_path, tmp_path, "PROBE-ID")
        text = " ".join(cmd)
        assert "PROBE-ID" in text, name
        assert "{" not in text, name
        assert "console" not in cfg, name


def test_hw_map_is_ignored():
    """An untracked hw-map.yml would make the safety repo dirty for run.py."""
    out = trees.git("check-ignore", "-v", str(hwmap.DEFAULT), cwd=hwmap.BENCH_DIR)
    assert ".gitignore" in out
