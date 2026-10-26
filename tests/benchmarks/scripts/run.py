#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Run a latency experiment from pinned, clean trees and record its provenance.

    run.py experiments/<name>.yaml --out <dir> [--only ID ...] [--dry-run]

Rules (a run stops before it builds anything if one is broken):

- The safety repo that holds this script and the experiment file is clean.
- Each tree of the experiment is at its pinned rev in trees.yaml and clean
  (scripts/trees.py setup creates the trees).
- The Zephyr SDK has the pinned version.
- The build uses only the modules of the tree (ZEPHYR_MODULES), not the
  modules of a west workspace.
- The hardware map of the host (hw-map.yml, twister format, not checked in)
  has one connected entry for the board, with the fixture
  "latbench_loopback". It gives the probe and the console (scripts/hwmap.py).

Output: <out>/<experiment>/<UTC time>/ with manifest.json (all revs, tool
versions, commands) and <tree>/<point>/ with rep<N>.log, the .config, the
devicetree, zephyr.elf and build.log. summary.txt has the percentiles.
src/ is the snapshot of the committed safety repo (git archive) that the
run built from. Each build also gets it as the Zephyr module "safety".

Experiment file:

    name: irq-smoke
    app: irq_latency                    # folder in tests/benchmarks
    board: nucleo_g474re                # optional, a key of boards.yaml
    trees: [ws-safety]
    repeat: 1
    timeout: 600                        # s per repetition
    common:                             # added to every point
      kconfig: {LATBENCH_SAMPLES: 100000}
      conf_files: [common/conf/lean.conf]       # relative to tests/benchmarks
    axes:                               # cartesian product, id = values joined by '-'
      path:
        stock: {kconfig: {LATBENCH_IRQ_PATH_STOCK: y}}
        direct: {...}
      anchor:
        default: {}
    points:                             # or explicit points (also allowed together)
      - id: direct-busy
        kconfig: {...}
"""

import argparse
import atexit
import datetime
import hashlib
import itertools
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hwmap  # noqa: E402
import latbench  # noqa: E402
import trees  # noqa: E402

BENCH_DIR = trees.BENCH_DIR


def fail(msg):
    sys.exit(f"error: {msg}")


def tool_version(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        return None
    return (r.stdout or r.stderr).strip().splitlines()[0]


def merge(a, b):
    out = {
        "kconfig": {**a.get("kconfig", {}), **b.get("kconfig", {})},
        "conf_files": a.get("conf_files", []) + b.get("conf_files", []),
        "dtc_overlays": a.get("dtc_overlays", []) + b.get("dtc_overlays", []),
    }
    return out


def expand_points(exp):
    common = exp.get("common", {})
    points = []
    axes = exp.get("axes", {})
    if axes:
        for axis, values in axes.items():
            bad = [k for k in values if not isinstance(k, str)]
            if bad:
                # YAML reads on/off/yes/no/true/false as booleans.
                fail(f"axis '{axis}': value names must be strings, not {bad} (quote them or rename them)")
        names = list(axes)
        for combo in itertools.product(*(axes[n].items() for n in names)):
            spec = common
            for _, value in combo:
                spec = merge(spec, value or {})
            spec["id"] = "-".join(k for k, _ in combo)
            spec["axes"] = {n: k for n, (k, _) in zip(names, combo)}
            points.append(spec)
    for p in exp.get("points", []):
        spec = merge(common, p)
        spec["id"] = p["id"]
        spec["axes"] = {}
        points.append(spec)
    ids = [p["id"] for p in points]
    if len(ids) != len(set(ids)):
        fail(f"duplicate point ids: {ids}")
    return points


def kconfig_value(v):
    if v is True:
        return "y"
    if v is False:
        return "n"
    return str(v)


def safety_repo_state():
    root = Path(trees.git("rev-parse", "--show-toplevel", cwd=BENCH_DIR))
    rev, dirty = trees.repo_state(root)
    return root, rev, dirty


def flash_command(board_cfg, zephyr, pdir, probe):
    """Return one command that runs the flash commands of the board in order."""
    fields = {"zephyr": str(zephyr), "elf": str(pdir / "zephyr.elf"), "hex": str(pdir / "zephyr.hex"),
              "probe": probe}
    cmds = [[arg.format(**fields) for arg in cmd] for cmd in board_cfg["flash"]]
    if len(cmds) == 1:
        return cmds[0]
    return ["sh", "-c", " && ".join(shlex.join(c) for c in cmds)]


def export_rev(repo_root, rev, dest):
    """Export the whole repo at rev to dest (git archive exports only the subfolder it runs in)."""
    dest.mkdir(parents=True, exist_ok=True)
    archive = subprocess.Popen(["git", "archive", "--format=tar", rev], cwd=repo_root, stdout=subprocess.PIPE)
    subprocess.run(["tar", "-x", "-C", str(dest)], stdin=archive.stdout, check=True)
    if archive.wait() != 0:
        fail(f"git archive {rev} failed")


def export_snapshot(repo_root, rev, dest):
    """Export the safety repo at rev to dest; return the bench folder in dest.

    A run builds from this snapshot, not from the worktree, so that work in
    the worktree during a long run cannot change what the run builds. The
    snapshot is also the Zephyr module "safety" of each build (see
    build_point()).
    """
    export_rev(repo_root, rev, dest)
    if not (dest / "zephyr" / "module.yml").is_file():
        fail(f"the safety repo at {rev} has no zephyr/module.yml")
    return dest / BENCH_DIR.relative_to(repo_root)


def check_config(config_file, kconfig):
    """Return the requested symbols that do not have their value in the .config.

    Kconfig only warns about a symbol that the tree does not have or whose
    dependencies are not met, and then builds with the default. This check
    makes that an error.
    """
    have = {}
    for line in Path(config_file).read_text().splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key, _, value = line.partition("=")
            have[key[len("CONFIG_"):]] = value.strip('"')
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            have[line[len("# CONFIG_"):-len(" is not set")]] = "n"
    bad = []
    for sym, value in kconfig.items():
        want = kconfig_value(value)
        got = have.get(sym, "n")
        if got != want:
            bad.append(f"{sym}: requested {want}, .config has {got}")
    return bad


def build_env(zephyr, sdk):
    """Return the environment of a build: no ZEPHYR_* variable of the caller, the tree and the SDK."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("ZEPHYR_")}
    env.update(
        ZEPHYR_BASE=str(zephyr),
        ZEPHYR_TOOLCHAIN_VARIANT="zephyr",
        ZEPHYR_SDK_INSTALL_DIR=str(sdk),
    )
    return env


def run_build(args, env, bdir, log, name):
    """Run CMake (args) and Ninja for one point; the output goes to log."""
    with open(log, "w") as f:
        f.write("$ " + shlex.join(args) + "\n")
        f.flush()
        for cmd in (args, ["ninja", "-C", str(bdir)]):
            r = subprocess.run(cmd, env=env, stdout=f, stderr=subprocess.STDOUT)
            if r.returncode != 0:
                fail(f"build failed for {name}, see {log}")


def build_point(tree_cfg, tree, point, src_bench, app, src_rev, board, board_cfg, sdk, bdir, log):
    """Build one point. The modules are those of the board from the tree, plus the
    safety snapshot (two folders above src_bench) as the module "safety".
    """
    app_dir = src_bench / app
    zephyr = trees.repo_dir(tree_cfg, tree, "zephyr")
    modules = [str(trees.repo_dir(tree_cfg, tree, name)) for name in board_cfg["modules"]]
    modules.append(str(src_bench.parents[1]))
    args = [
        "cmake",
        "-GNinja",
        "-S",
        str(app_dir),
        "-B",
        str(bdir),
        f"-DBOARD={board}",
        f"-DZEPHYR_MODULES={';'.join(modules)}",
    ]
    if point["conf_files"]:
        args.append("-DEXTRA_CONF_FILE=" + ";".join(str(src_bench / f) for f in point["conf_files"]))
    if point["dtc_overlays"]:
        args.append("-DEXTRA_DTC_OVERLAY_FILE=" + ";".join(str(src_bench / f) for f in point["dtc_overlays"]))
    args.append(f"-DLATBENCH_SRC_REV={src_rev}")
    for sym, value in point["kconfig"].items():
        args.append(f"-DCONFIG_{sym}={kconfig_value(value)}")

    run_build(args, build_env(zephyr, sdk), bdir, log, f"{tree}/{point['id']}")
    bad = check_config(bdir / "zephyr" / ".config", point["kconfig"])
    if bad:
        fail(f"Kconfig values not applied for {tree}/{point['id']}:\n  " + "\n  ".join(bad))
    return args


def find_points(path, only=None):
    """Return (run folder, manifest, entries) for a run folder or a point folder <run>/<tree>/<point>."""
    path = Path(path).resolve()
    if (path / "manifest.json").is_file():
        run_dir, want = path, None
    elif len(path.parents) > 1 and (path.parents[1] / "manifest.json").is_file():
        run_dir, want = path.parents[1], (path.parent.name, path.name)
    else:
        fail(f"{path} is not a run folder or a point folder of a run")
    manifest = json.loads((run_dir / "manifest.json").read_text())
    entries = [
        e for e in manifest["points"]
        if (want is None or (e["tree"], e["id"]) == want) and (not only or e["id"] in only)
    ]
    if not entries:
        fail(f"no points to rebuild in {path}")
    return run_dir, manifest, entries


def move_paths(cmake, moves, bdir):
    """Return the CMake command of a point with the build folder bdir and each old folder of moves replaced."""
    out = []
    for i, arg in enumerate(cmake):
        if i > 0 and cmake[i - 1] == "-B":
            out.append(str(bdir))
            continue
        for old, new in moves.items():
            arg = new if arg == old else arg.replace(old + "/", new + "/")
        out.append(arg)
    return out


def cmake_cache_value(bdir, key):
    """Return the value of key in the CMakeCache.txt of a build, or None."""
    cache = bdir / "CMakeCache.txt"
    if cache.exists():
        for line in cache.read_text().splitlines():
            if line.startswith(key + ":"):
                return line.partition("=")[2]
    return None


def elf_image(elf, objcopy, tmp):
    """Return the loadable sections of an ELF as Intel HEX: the flashed image, without debug information."""
    out = tmp / "image.hex"
    subprocess.run([objcopy, "-O", "ihex", str(elf), str(out)], check=True)
    image = out.read_bytes()
    out.unlink()
    return image


def compare_point(pdir, bdir, elf_sha256, objcopy=None, tmp=None):
    """Return (same, different) file names of the stored files of a point and a new build.

    If the ELF hashes differ (the debug information has the build folder) and
    objcopy is given, "ELF image" compares the loadable sections of the two ELFs.
    """
    same, diff = [], []
    elf = bdir / "zephyr" / "zephyr.elf"
    sha = hashlib.sha256(elf.read_bytes()).hexdigest() if elf.exists() else None
    (same if sha == elf_sha256 else diff).append("zephyr.elf")
    if sha and sha != elf_sha256 and objcopy and (pdir / "zephyr.elf").exists():
        old = elf_image(pdir / "zephyr.elf", objcopy, tmp)
        (same if old == elf_image(elf, objcopy, tmp) else diff).append("ELF image")
    for name in ("zephyr.hex", ".config", "zephyr.dts"):
        old, new = pdir / name, bdir / "zephyr" / name
        if old.exists():
            (same if new.exists() and new.read_bytes() == old.read_bytes() else diff).append(name)
    return same, diff


def rebuild(args):
    """Build the points of an old run again, from its snapshot and manifest, and compare the images.

    The flashed image (zephyr.hex, or zephyr.elf if the run has no hex) and
    the .config must be the same. The ELF has the build folder in its debug
    information, so the build goes to the original build folder if it is free.
    """
    run_dir, manifest, entries = find_points(args.rebuild, args.only)
    old_run = Path(entries[0]["cmake"][entries[0]["cmake"].index("-B") + 1]).parents[2]
    moves = {str(old_run): str(run_dir)}
    cfg = {
        "root": Path(args.trees_root or manifest["trees_root"]).expanduser(),
        "trees": manifest["trees"],
        "toolchain": {"zephyr_sdk": {"path": manifest["toolchain"]["path"],
                                     "version": manifest["toolchain"]["zephyr_sdk"]}},
    }
    try:
        sdk = trees.check_toolchain(cfg)
        for t in sorted({e["tree"] for e in entries}):
            trees.check_tree(cfg, t)
    except trees.TreeError as e:
        fail(str(e))

    import tempfile

    # The logs and the builds that cannot go to the original folder. Kept if a point fails.
    tmp = Path(tempfile.mkdtemp(prefix="latbench-rebuild-"))
    if "snapshot" not in manifest["safety"]:
        # An old run that built from the worktree. Its build took the revision
        # string from "git describe" and had no -DLATBENCH_SRC_REV, so an export
        # without .git gives another image: use a temporary worktree instead.
        safety = manifest["safety"]
        repo_root, _, _ = safety_repo_state()
        if trees.git("cat-file", "-t", safety["rev"], cwd=repo_root, check=False) != "commit":
            fail(f"the run has no snapshot, and the safety revision {safety['rev']} is not in {repo_root}")
        src = tmp / "src"
        trees.git("worktree", "add", "--detach", str(src), safety["rev"], cwd=repo_root)
        atexit.register(trees.git, "worktree", "remove", "--force", str(src), cwd=repo_root, check=False)
        moves[safety["path"]] = str(src)
    print(f"rebuild {run_dir}  {len(entries)} points")
    failed = 0
    for e in entries:
        name = f"{e['tree']}/{e['id']}"
        pdir = run_dir / e["tree"] / e["id"]
        bdir = pdir / "build"
        if bdir.exists() or run_dir != old_run:
            bdir = tmp / e["tree"] / e["id"]
        bdir.mkdir(parents=True)
        bad = True
        try:
            cmake = move_paths(e["cmake"], moves, bdir)
            run_build(cmake, build_env(trees.repo_dir(cfg, e["tree"], "zephyr"), sdk), bdir,
                      tmp / f"{e['tree']}-{e['id']}.log", name)
            same, diff = compare_point(pdir, bdir, e["elf_sha256"], cmake_cache_value(bdir, "CMAKE_OBJCOPY"), tmp)
            if (pdir / "zephyr.hex").exists():
                image_same = "zephyr.hex" in same
            else:
                image_same = "zephyr.elf" in same or "ELF image" in same
            bad = not image_same or ".config" in diff
        finally:
            # The result folder stays as it was; a build that failed or is different goes to tmp.
            if not args.keep_build and bdir.is_relative_to(pdir):
                if bad:
                    (tmp / e["tree"]).mkdir(exist_ok=True)
                    shutil.move(bdir, tmp / e["tree"] / e["id"])
                else:
                    shutil.rmtree(bdir)
        failed += bad
        print(f"[{name}] {'DIFFERENT' if bad else 'same'}: same {', '.join(same) or '-'}"
              + (f"; different {', '.join(diff)}" if diff else ""), flush=True)
    print(f"{len(entries) - failed} of {len(entries)} points give the same image and .config")
    if failed or args.keep_build:
        print(f"logs and builds in {tmp}")
    else:
        shutil.rmtree(tmp)
    if failed:
        sys.exit(1)


def select_hardware(args, board, zephyr):
    """Return the probe and console of the board: from the hardware map, or from --probe and --port."""
    if args.port and args.probe:
        return {"platform": [board], "probe": args.probe, "id": args.probe, "product": None, "runner": None,
                "serial": args.port, "baud": 115200, "fixtures": [], "notes": "from --probe and --port"}
    try:
        schema = zephyr / hwmap.SCHEMA
        entries = hwmap.load(args.hardware_map, schema if schema.is_file() else None)
        hw = hwmap.hardware(hwmap.select(entries, board, args.probe, args.hardware_map))
    except hwmap.HwMapError as e:
        fail(str(e))
    hw["map"] = str(Path(args.hardware_map).resolve())
    if args.port:
        hw["serial"] = args.port
    return hw


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("experiment", nargs="?")
    p.add_argument("--out")
    p.add_argument("--rebuild", metavar="RUN",
                   help="build the points of a run folder (or of one <run>/<tree>/<point> folder) again"
                        " and compare them with the stored images; does not flash")
    p.add_argument("--trees-root")
    p.add_argument("--hardware-map", default=str(hwmap.DEFAULT),
                   help=f"hardware map of the host (default: {hwmap.DEFAULT.relative_to(BENCH_DIR)})")
    p.add_argument("--probe", help="probe id: select the entry of the hardware map; with --port, no map is necessary")
    p.add_argument("--port", help="serial port of the console (default: serial of the entry in the hardware map)")
    p.add_argument("--only", nargs="*", help="run only these point ids")
    p.add_argument("--dry-run", action="store_true", help="check and list the points, do not build")
    p.add_argument("--build-only", action="store_true", help="build each point in a temporary folder, do not flash")
    p.add_argument("--keep-build", action="store_true")
    args = p.parse_args()
    if args.rebuild:
        if args.experiment or args.out:
            p.error("--rebuild takes no experiment and no --out")
        rebuild(args)
        return
    if not args.experiment or not args.out:
        p.error("an experiment and --out are necessary")

    exp_path = Path(args.experiment).resolve()
    exp_text = exp_path.read_text()
    exp = yaml.safe_load(exp_text)

    # 1. Provenance checks, before anything is built.
    repo_root, repo_rev, repo_dirty = safety_repo_state()
    if repo_dirty:
        fail(f"safety repo {repo_root} is dirty, commit first:\n{repo_dirty}")
    if not exp_path.is_relative_to(repo_root):
        fail(f"{exp_path} is not in the safety repo {repo_root}")

    tree_cfg = trees.load(args.trees_root)
    boards = trees.load_boards()
    board = exp.get("board", boards["default"])
    try:
        repos = trees.board_repos(boards, board)
        sdk = trees.check_toolchain(tree_cfg)
        for t in exp["trees"]:
            if t not in tree_cfg["trees"]:
                raise trees.TreeError(f"unknown tree '{t}'")
            trees.check_tree_has(tree_cfg, t, repos)
            trees.check_tree(tree_cfg, t, repos)
    except trees.TreeError as e:
        fail(str(e))
    board_cfg = boards["boards"][board]
    if not (BENCH_DIR / exp["app"]).is_dir():
        fail(f"no app folder {exp['app']}")
    points = expand_points(exp)
    if args.only:
        points = [pt for pt in points if pt["id"] in args.only]
    if not points:
        fail("no points to run")

    print(f"safety {repo_rev[:12]}  trees {', '.join(exp['trees'])}  {len(points)} points x {exp.get('repeat', 1)}")
    for pt in points:
        print(f"  {pt['id']}: {pt['kconfig']} {pt['conf_files']} {pt['dtc_overlays']}")
    if args.dry_run:
        return
    if not args.build_only:
        hw = select_hardware(args, board, trees.repo_dir(tree_cfg, exp["trees"][0], "zephyr"))
        port = hw["serial"]
        print(f"board {board}: probe {hw['probe']} ({hw['product']}), console {port}")
    if args.build_only:
        import tempfile

        # With --keep-build the folder stays, for example to compare the images of two trees.
        tmp = tempfile.mkdtemp(prefix="latbench-build-")
        src_bench = export_snapshot(repo_root, repo_rev, Path(tmp) / "src")
        for tree in exp["trees"]:
            for pt in points:
                bdir = Path(tmp) / tree / pt["id"]
                bdir.mkdir(parents=True)
                print(f"[{tree}/{pt['id']}] build", flush=True)
                build_point(tree_cfg, tree, pt, src_bench, exp["app"], repo_rev, board, board_cfg, sdk,
                            bdir / "build", bdir / "build.log")
        print("all points build")
        if args.keep_build:
            print(f"builds in {tmp}")
        else:
            shutil.rmtree(tmp)
        return

    # 2. Output folder and manifest.
    started = datetime.datetime.now(datetime.timezone.utc)
    run_dir = Path(args.out).resolve() / exp["name"] / started.strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True)
    src_bench = export_snapshot(repo_root, repo_rev, run_dir / "src")
    probe = subprocess.run(
        ["udevadm", "info", "--query=property", port], capture_output=True, text=True
    ).stdout
    probe_serial = next((ln.split("=", 1)[1] for ln in probe.splitlines() if ln.startswith("ID_SERIAL_SHORT=")), None)

    import serial

    manifest = {
        "experiment": exp["name"],
        "experiment_file": str(exp_path.relative_to(repo_root)),
        "experiment_yaml": exp_text,
        "command": shlex.join(sys.argv),
        "started": started.isoformat(),
        "host": platform.node(),
        "safety": {"path": str(repo_root), "rev": repo_rev, "snapshot": str(src_bench.relative_to(run_dir)),
                   "module": str(src_bench.parents[1].relative_to(run_dir))},
        "trees": {
            t: {**tree_cfg["trees"][t], "repos": {r: tree_cfg["trees"][t]["repos"][r] for r in repos}}
            for t in exp["trees"]
        },
        "trees_root": str(tree_cfg["root"]),
        "toolchain": {"zephyr_sdk": str(tree_cfg["toolchain"]["zephyr_sdk"]["version"]), "path": str(sdk)},
        "tools": {
            "cmake": tool_version(["cmake", "--version"]),
            "ninja": tool_version(["ninja", "--version"]),
            # The tools that flash this board (first word of each flash command).
            **{cmd[0]: tool_version([cmd[0], "--version"]) for cmd in board_cfg["flash"]},
            "python": sys.version.split()[0],
            "pyserial": serial.__version__,
        },
        "board": board,
        "board_cfg": board_cfg,
        "hardware": hw,
        "console": port,
        "probe_serial": probe_serial,
        "points": [],
    }
    manifest_file = run_dir / "manifest.json"

    def save_manifest():
        manifest_file.write_text(json.dumps(manifest, indent=2) + "\n")

    save_manifest()

    # 3. Build, flash and capture each point.
    logs = []
    for tree in exp["trees"]:
        zephyr = trees.repo_dir(tree_cfg, tree, "zephyr")
        for pt in points:
            pdir = run_dir / tree / pt["id"]
            bdir = pdir / "build"
            pdir.mkdir(parents=True)
            print(f"[{tree}/{pt['id']}] build", flush=True)
            cmake_args = build_point(tree_cfg, tree, pt, src_bench, exp["app"], repo_rev, board, board_cfg, sdk,
                                     bdir, pdir / "build.log")
            elf = bdir / "zephyr" / "zephyr.elf"
            for f in (elf, bdir / "zephyr" / "zephyr.hex", bdir / "zephyr" / ".config", bdir / "zephyr" / "zephyr.dts"):
                if f.exists():
                    shutil.copy2(f, pdir / f.name)
            entry = {
                "tree": tree,
                "id": pt["id"],
                "axes": pt["axes"],
                "kconfig": pt["kconfig"],
                "conf_files": pt["conf_files"],
                "dtc_overlays": pt["dtc_overlays"],
                "cmake": cmake_args,
                "elf_sha256": hashlib.sha256(elf.read_bytes()).hexdigest(),
                "logs": [],
            }
            manifest["points"].append(entry)
            flash_cmd = flash_command(board_cfg, zephyr, pdir, hw["probe"])
            for rep in range(1, exp.get("repeat", 1) + 1):
                log = pdir / f"rep{rep}.log"
                print(f"[{tree}/{pt['id']}] rep {rep}", flush=True)
                try:
                    latbench.run_capture(log, flash_cmd, port, baud=hw["baud"], timeout=exp.get("timeout", 600))
                except latbench.CaptureError as e:
                    entry["error"] = str(e)
                    save_manifest()
                    fail(f"{tree}/{pt['id']} rep {rep}: {e}")
                entry["logs"].append(str(log.relative_to(run_dir)))
                logs.append(log)
                save_manifest()
            if not args.keep_build:
                shutil.rmtree(bdir)

    manifest["finished"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save_manifest()

    # 4. Summary.
    with open(run_dir / "summary.txt", "w") as f:
        sys.stdout = f
        try:
            latbench.summary(argparse.Namespace(logs=[str(x) for x in logs], json=False))
        finally:
            sys.stdout = sys.__stdout__
    print((run_dir / "summary.txt").read_text())
    print(f"results in {run_dir}")


if __name__ == "__main__":
    main()
