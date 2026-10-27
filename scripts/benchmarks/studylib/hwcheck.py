# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The loopback wire check of a board (study.py lab hwcheck): hardware, not data.

Builds the app tests/benchmarks/loopback_check for the board from a pinned
tree, flashes it with the flash commands of boards.yaml and reads the
console until the line "RESULT: OK" or "RESULT: FAIL". The build folder
is in the lab space (.lab/hwcheck/<board>). The check writes no result
data; a campaign records its outcome in the campaign record.
"""

import subprocess
import time

import hwmap
import trees

TIMEOUT = 60


class HwCheckError(Exception):
    pass


def tree_for(cfg, repos):
    """The first tree of trees.yaml that pins all repos (zephyr and the board modules)."""
    for name, t in cfg["trees"].items():
        if all(r in t["repos"] for r in repos):
            return name
    raise HwCheckError(f"no tree pins {repos}")


def check(lab, board, log=print, tree=None):
    """Return (ok, lines). Raise HwCheckError if it cannot run (build, flash, no board)."""
    import serial

    import run

    cfg = trees.load(lab=lab)
    boards = trees.load_boards()
    repos = trees.board_repos(boards, board)
    tree = tree or tree_for(cfg, repos)
    trees.check_tree(cfg, tree, repos)
    sdk = trees.check_toolchain(cfg)
    bcfg = boards["boards"][board]
    zephyr = trees.repo_dir(cfg, tree, "zephyr")
    schema = zephyr / hwmap.SCHEMA
    hw = hwmap.hardware(hwmap.select(hwmap.load(lab.hw_map, schema if schema.is_file() else None), board,
                                     path=str(lab.hw_map)))
    bdir = lab.folder / ".lab" / "hwcheck" / board.replace("/", "_").replace("@", "_")
    modules = [str(trees.repo_dir(cfg, tree, m)) for m in bcfg["modules"]]
    cmd = ["cmake", "-GNinja", "-S", str(trees.BENCH_DIR / "loopback_check"), "-B", str(bdir), f"-DBOARD={board}",
           "-DZEPHYR_MODULES=" + ";".join(modules), f"-DWEST_TOPDIR={cfg['root'] / tree}"]
    env = run.build_env(zephyr, sdk)
    log(f"{board}: build loopback_check ({tree})")
    for c in (cmd, ["ninja", "-C", str(bdir)]):
        r = subprocess.run(c, env=env, capture_output=True, text=True)
        if r.returncode:
            raise HwCheckError(f"build failed: {' '.join(c)}\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}")
    flash = run.flash_command(bcfg, zephyr, bdir / "zephyr", hw["probe"])
    log(f"{board}: flash, probe {hw['probe']}, console {hw['serial']}")
    lines = []
    with serial.Serial(hw["serial"], hw["baud"], timeout=1) as s:
        s.reset_input_buffer()
        r = subprocess.run(flash, capture_output=True, text=True)
        if r.returncode:
            raise HwCheckError(f"flash failed: {' '.join(flash)}\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
        end = time.time() + TIMEOUT
        while time.time() < end:
            line = s.readline().decode(errors="replace").rstrip()
            if line:
                lines.append(line)
            if line.startswith("RESULT:"):
                return "OK" in line, lines
    raise HwCheckError(f"no RESULT line in {TIMEOUT} s: {lines[-5:]}")
