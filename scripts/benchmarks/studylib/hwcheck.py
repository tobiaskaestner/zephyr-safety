# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The loopback wire check of a board (study.py lab hwcheck): hardware, not data.

Builds the app tests/benchmarks/loopback_check for the board from a pinned
tree (with the build cache, like the points of a run: run.Builder), flashes
it with the flash commands of boards.yaml and reads the console until the
line "RESULT: OK" or "RESULT: FAIL". Each check writes the record
.lab/hwcheck/<board>.json: the time, the host, the tree, the image (digest,
cache key, from build or cache), the result and all console lines. A
campaign refers to that record. If the design repo has changes that are
not committed, the image cannot go into the cache: the check builds in
.lab/hwcheck/<board>/ and the record says "dirty".
"""

import datetime
import hashlib
import platform
import subprocess
import time

import hwmap
import trees

TIMEOUT = 60


class HwCheckError(Exception):
    pass


def tree_for(cfg, repos):
    """The first tree of validation/trees/ (by name) that pins all repos (zephyr and the board modules)."""
    for name, t in cfg["trees"].items():
        if all(r in t["repos"] for r in repos):
            return name
    raise HwCheckError(f"no tree pins {repos}")


def record_path(lab, board):
    return lab.folder / ".lab" / "hwcheck" / f"{board.replace('/', '_').replace('@', '_')}.json"


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
    started = datetime.datetime.now(datetime.timezone.utc)
    pdir = lab.folder / ".lab" / "hwcheck" / board.replace("/", "_").replace("@", "_")
    if pdir.exists():
        import shutil
        shutil.rmtree(pdir)
    pdir.mkdir(parents=True)
    repo_root, repo_rev, dirty = run.safety_repo_state()
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
            cmake = run.build_point(cfg, tree, point, trees.BENCH_DIR, "loopback_check", "dirty", board, bcfg, sdk,
                                    pdir / "build", pdir / "build.log", b.build_version(tree), b.builder)
            built = {"cmake": cmake, "build": {"from": "build (dirty repo, no cache)"}}
            from . import images
            for f in ("zephyr.elf", "zephyr.hex"):
                if (pdir / "build" / "zephyr" / f).is_file():
                    (pdir / images.names("loopback_check", tree, "default")[f]).write_bytes(
                        (pdir / "build" / "zephyr" / f).read_bytes())
    except SystemExit as e:
        raise HwCheckError(f"build failed: {e}") from None
    flash = run.flash_command(bcfg, zephyr, pdir, hw["probe"])
    log(f"{board}: flash, probe {hw['probe']}, console {hw['serial']}")
    lines, ok = [], None
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
                ok = "OK" in line
                break
    from . import images, jsonout
    elf = images.find(pdir, ".elf")
    rec = {"format": "latbench-hwcheck/1", "board": board, "host": platform.node(), "time": started.isoformat(),
           "tree": tree, "repo": {"rev": repo_rev, "dirty": bool(dirty)}, "probe": hw["probe"],
           "console": hw["serial"], "image": {"elf_sha256": hashlib.sha256(elf.read_bytes()).hexdigest() if elf else None,
                                              **built.get("build", {})},
           "result": None if ok is None else ("ok" if ok else "fail"), "lines": lines}
    jsonout.write(record_path(lab, board), rec)
    if ok is None:
        raise HwCheckError(f"no RESULT line in {TIMEOUT} s: {lines[-5:]}")
    return ok, lines
