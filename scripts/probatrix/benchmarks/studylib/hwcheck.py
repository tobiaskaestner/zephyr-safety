# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The loopback wire check of a board (study.py lab hwcheck): hardware, not data.

Builds the app tests/benchmarks/loopback_check for the board from a pinned
tree (with the build cache, like the points of a run: run.Builder), flashes
it with the flash commands of boards.yaml and reads the console until the
line "RESULT: OK" or "RESULT: FAIL". Each check writes its record
.lab/hwcheck/history/<board>/<UTC>.json (also a check that cannot run:
result "error"), and a copy as .lab/hwcheck/<board>.json: the time, the
host, the tree, the image (digest, cache key, from build or cache), the
result and all console lines. A campaign names the record of each check.
The check takes the board lock (as a campaign does), unless a campaign
that holds it runs the check, and opens the console exclusively. If the design repo has changes that are
not committed, the image cannot go into the cache: the check builds in
.lab/hwcheck/<board>/ and the record says "dirty".
"""

import datetime
import hashlib
import os
import platform
import subprocess
import time

from probatrix.benchmarks import kind as benchkind
from probatrix.benchmarks import hwmap
from probatrix.benchmarks import trees

TIMEOUT = 60


AXIS = benchkind.KIND.instance_axis      # the instance axis (the board) of the kind


class HwCheckError(Exception):
    pass


def tree_for(cfg, repos):
    """The first tree (by name) that pins all repos (zephyr and the board modules) and that this lab
    space set up; else the first that pins them (its check then says "not set up")."""
    pinning = [name for name, t in cfg["trees"].items() if all(r in t["repos"] for r in repos)]
    if not pinning:
        raise HwCheckError(f"no tree pins {repos}")
    ready = [t for t in pinning if trees.tree_state(cfg, t, repos)[0] == "ok"]
    return (ready or pinning)[0]


def board_tag(board):
    return AXIS.lock_key(board)


def record_path(lab, board):
    """The record of the newest check of a board (a copy of the newest history record)."""
    return lab.folder / ".lab" / "hwcheck" / f"{board_tag(board)}.json"


def history_path(lab, board, started):
    """The record of one check: .lab/hwcheck/history/<board>/<UTC>.json (each check keeps its own)."""
    return lab.folder / ".lab" / "hwcheck" / "history" / board_tag(board) / f"{started:%Y%m%dT%H%M%SZ}.json"


def check(lab, board, log=print, tree=None, locked=False):
    """Return (ok, lines, record). Raise HwCheckError if it cannot run (build, flash, no RESULT line);
    the error has .record. Each check writes its record, also a failed one (history_path) and the
    copy record_path. locked: the caller (a campaign) holds the board lock; else the check takes it."""
    from . import campaign
    started = datetime.datetime.now(datetime.timezone.utc)
    cid = f"lab-hwcheck-{os.getpid()}"
    if not locked:
        campaign.take_lock(lab, cid, [board])
    rec = {"format": "latbench-hwcheck/2", "board": board, "host": platform.node(), "time": started.isoformat(),
           "result": "error", "lines": []}
    try:
        ok, lines = _check(lab, board, log, tree, rec)
        rec["result"] = "ok" if ok else "fail"
        return ok, lines, _write(lab, board, started, rec)
    except (HwCheckError, trees.TreeError, hwmap.HwMapError, OSError) as e:
        rec["error"] = f"{type(e).__name__}: {e}"
        path = _write(lab, board, started, rec)
        err = e if isinstance(e, HwCheckError) else HwCheckError(rec["error"])
        err.record = path
        raise err from None
    finally:
        if not locked:
            campaign.drop_lock(lab, cid)


def _write(lab, board, started, rec):
    from probatrix.core import jsonout
    path = history_path(lab, board, started)
    jsonout.write(path, rec)
    jsonout.write(record_path(lab, board), rec)
    return path


def _check(lab, board, log, tree, rec):
    import serial

    from . import kindhooks

    run = kindhooks.run_module()
    cfg = trees.load(lab=lab)
    boards = trees.load_boards()
    repos = trees.board_repos(boards, board)
    tree = tree or tree_for(cfg, repos)
    rec["tree"] = tree
    trees.check_tree(cfg, tree, repos)
    sdk = trees.check_toolchain(cfg)
    bcfg = boards["boards"][board]
    zephyr = trees.repo_dir(cfg, tree, "zephyr")
    schema = zephyr / hwmap.SCHEMA
    hw = hwmap.hardware(hwmap.select(hwmap.load(lab.hw_map, schema if schema.is_file() else None), board,
                                     path=str(lab.hw_map)))
    rec.update(probe=hw["probe"], console=hw["serial"])
    pdir = lab.folder / ".lab" / "hwcheck" / board_tag(board)
    if pdir.exists():
        import shutil
        shutil.rmtree(pdir)
    pdir.mkdir(parents=True)
    repo_root, repo_rev, dirty = run.safety_repo_state()
    rec["repo"] = {"rev": repo_rev, "dirty": bool(dirty)}
    exp = {"name": "loopback-check", "app": "loopback_check", "trees": [tree]}
    point = {"id": "default", "kconfig": {}, "conf_files": [], "dtc_overlays": []}
    log(f"{board}: build loopback_check ({tree})")
    try:
        if not dirty:
            from . import buildcache
            b = run.Builder(exp, cfg, repos, board, bcfg, sdk, repo_root, repo_rev, buildcache.Cache(lab.build_cache),
                            log=lambda m: None)
            built = b.build(tree, point, pdir)
        else:
            b = run.Builder(exp, cfg, repos, board, bcfg, sdk, repo_root, repo_rev, None, log=lambda m: None)
            b.bench_tree = "dirty"
            cmake = run.build_point(cfg, tree, point, benchkind.KIND.bench_dir, "loopback_check", "dirty", board, bcfg, sdk,
                                    pdir / "build", pdir / "build.log", b.build_version(tree), b.builder)
            built = {"cmake": cmake, "build": {"from": "build (dirty repo, no cache)"}}
            from . import images
            for f in ("zephyr.elf", "zephyr.hex"):
                if (pdir / "build" / "zephyr" / f).is_file():
                    (pdir / images.names("loopback_check", tree, "default")[f]).write_bytes(
                        (pdir / "build" / "zephyr" / f).read_bytes())
    except SystemExit as e:
        raise HwCheckError(f"build failed: {e}") from None
    from . import images
    elf = images.find(pdir, ".elf")
    rec["image"] = {"elf_sha256": hashlib.sha256(elf.read_bytes()).hexdigest() if elf else None,
                    **built.get("build", {})}
    flash = run.flash_command(bcfg, zephyr, pdir, hw["probe"])
    log(f"{board}: flash, probe {hw['probe']}, console {hw['serial']}")
    lines, ok = rec["lines"], None
    with serial.Serial(hw["serial"], hw["baud"], timeout=1, exclusive=True) as s:
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
                ok = "OK" in line
                break
    if ok is None:
        raise HwCheckError(f"no RESULT line in {TIMEOUT} s: {lines[-5:]}")
    return ok, lines
