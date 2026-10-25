# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Checks of the experiment files (no build, no board).

Kconfig only warns about a value that it cannot apply, and run.py finds it
only after the build. These checks find such errors in the experiment
files before a run.
"""

import sys
from pathlib import Path

import pytest
import yaml

SCRIPTS = Path(__file__).resolve().parent.parent
BENCH = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import run  # noqa: E402
import trees  # noqa: E402

EXPERIMENTS = sorted((BENCH / "experiments").glob("*.yaml"))
PLACES = ("LATBENCH_CODE_FLASH", "LATBENCH_CODE_FLASH_PAD", "LATBENCH_CODE_RAM")


def points(path):
    return run.expand_points(yaml.safe_load(path.read_text()))


def is_y(kconfig, sym):
    return run.kconfig_value(kconfig.get(sym, "n")) == "y"


@pytest.mark.parametrize("path", EXPERIMENTS, ids=[p.stem for p in EXPERIMENTS])
def test_code_place(path):
    """The pad needs LATBENCH_CODE_FLASH_PAD or LATBENCH_CODE_RAM, and a point selects one place."""
    exp = yaml.safe_load(path.read_text())
    board = exp.get("board", trees.load_boards()["default"])
    port = BENCH / "common" / "boards" / trees.load_boards()["boards"][board]["port"]
    for pt in points(path):
        k = pt["kconfig"]
        places = [s for s in PLACES if is_y(k, s)]
        assert len(places) <= 1, f"{pt['id']}: more than one place: {places}"
        if "LATBENCH_CODE_PAD_BYTES" in k:
            pad = int(k["LATBENCH_CODE_PAD_BYTES"])
            assert places and places[0] != "LATBENCH_CODE_FLASH", (
                f"{pt['id']}: LATBENCH_CODE_PAD_BYTES needs LATBENCH_CODE_FLASH_PAD or LATBENCH_CODE_RAM")
            assert pad % 4 == 0, f"{pt['id']}: the pad must be a multiple of 4"
        if is_y(k, "LATBENCH_CODE_RAM") and "LATBENCH_CODE_RAM_REGION" not in k:
            assert (port / "Kconfig.port").is_file(), (
                f"{pt['id']}: LATBENCH_CODE_RAM, but the port {port.name} gives no RAM region")


def test_code_layout_selects_the_pad():
    """code-layout measures the flash pad, as the run 20261025T060257Z."""
    for pt in points(BENCH / "experiments" / "code-layout.yaml"):
        assert is_y(pt["kconfig"], "LATBENCH_CODE_FLASH_PAD"), pt["id"]
